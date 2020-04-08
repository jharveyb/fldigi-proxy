#!/usr/bin/python3.8

"""
Proxy TCP/IP connections over a radio via fldigi, and change
basic settings in fldigi to better send packets vs. text
"""

from time import sleep
from collections import deque
from functools import partial
import argparse
import pyfldigi
import codecs
import trio

# default ports: 7322 for ARQ, 7342 for TCP/IP, 7362 for XML, 8421 for fllog

class fl_instance:
    host_ip = '127.0.0.1'
    xml_port = 7362
    proxy_port = 22
    send_poll = 0.25
    send_delay = 3.0
    recv_poll = 1.0
    send_timeout_multiplier = 0.0
    modem_timeout_multipliers = {'BPSK63' : 1.0, 'PSK125R' : 0.5, 'PSK250R' : 0.25, 'PSK500R' : 0.125}
    # synchronize between radio_send and radio_recv to avoid collisions; states are 'RX', 'TX', or 'IDLE'
    radio_state = 'IDLE'
    # using instead of a lock since trio locks seem to only support release by the owner
    radio_state_semaphore = trio.Semaphore(1)
    base64_prefix = b'BTC'
    base64_suffix = b'\r\n'

    # we assume no port collisions for ARQ or XMLRPC ports
    def __init__(self, daemon=False, noproxy=False, host=host_ip, xmlport=xml_port,
                 proxyport=proxy_port, headless=False, wfall_only=False):
        self.host_ip = host
        if (xmlport != None):
            self.xml_port = xmlport
        if (noproxy == False):
            self.proxy_port = proxyport
        try:
            self.fl_client = pyfldigi.Client(hostname=self.host_ip, port=self.xml_port)
        except:
            print("pyfldigi client start failed! Check that ports aren't in use")
            return
        if (daemon == True):
            self.fl_app = pyfldigi.ApplicationMonitor(hostname=self.host_ip, port=self.xml_port)
            self.fl_app.start(headless=headless, wfall_only=wfall_only)
        else:
            self.fl_app = None

    def port_info(self):
        print("IP", self.host_ip, "XML-RPC port:", self.xml_port, "proxy port:", self.proxy_port)

    def version(self):
        return self.fl_client.version

    def clear_buffers(self):
        self.fl_client.text.clear_rx()
        self.fl_client.text.clear_tx()

    # assume we are in RX mode when calling (fldigi default state)
    # and reset to RX after send completes
    # binary data is base64-encoded and newline-terminated
    async def radio_send(self, tx_msg):
        self.fl_client.text.clear_rx()
        self.fl_client.text.clear_tx()
        msg_timeout = len(tx_msg) * self.send_timeout_multiplier
        print("Sending:", tx_msg)
        # timeout should be large enough for worst-case TX time / packet size
        # + buffer room for txmonitor to work; currently tuned to BPSK63 as modem
        self.fl_client.main.send(tx_msg, block=False, timeout=msg_timeout)
        # txmonitor thread swtiches mode to RX soon after send finishes
        while (self.fl_client.main.get_trx_state() != "RX"):
            await trio.sleep(self.send_poll)
        print("Sent!")
        # wait for txmonitor thread to fully reset
        await trio.sleep(self.send_delay)

    async def radio_send_test_task(self, tx_msg_list):
        for tx_msg in tx_msg_list:
            await self.radio_send(tx_msg)

    async def radio_send_task(self, packet_deque: deque):
        print("started radio_send_task")
        radio_buffer = bytes()
        while(True):
            await trio.sleep(self.send_poll)
            # never start a send while receiving on radio
            if (self.radio_state == 'RX'):
                continue
            elif (len(packet_deque) > 0 and self.radio_state == 'IDLE'):
                print("radio idle, starting a send")
                await self.radio_state_semaphore.acquire()
                self.radio_state = 'TX'
                self.radio_state_semaphore.release()
                print("radio state switched to TX, send imminent")
                radio_buffer = packet_deque.popleft()
                await self.radio_send(radio_buffer)
                print("finished send, setting radio state back to IDLE")
                await self.radio_state_semaphore.acquire()
                self.radio_state = 'IDLE'
                self.radio_state_semaphore.release()
                print("radio idle, waiting", self.send_delay, "seconds in send loop")
                # space out consecutive sends + allow for receives
                await trio.sleep(self.send_delay)

    # received content is raw bytes, newline-terminated
    async def radio_receive(self):
        rx_msg = bytes()
        rx_prefix = bytes()
        rx_prefix_check = False
        rx_fragment = bytes()
        while (True):
            await trio.sleep(self.recv_poll)
            # ignore received data while radio is busy
            if (self.radio_state == 'TX'):
                print("radio state is TX, cannot receive")
                continue
            # state already RX from earlier in the receive process
            elif (self.radio_state == 'RX'):
                print("radio already in RX state")
                pass
            # switch radio state to allow for receive
            elif (self.radio_state == 'IDLE'):
                print("radio idle, starting an RX poll")
                await self.radio_state_semaphore.acquire()
                self.radio_state = 'RX'
                self.radio_state_semaphore.release()
                print("radio switched to RX")
            # should only reach this if radio state is RX
            rx_fragment = self.fl_client.text.get_rx_data()
            if (isinstance(rx_fragment, bytes) and rx_fragment != b''):
                rx_msg += rx_fragment
                if rx_msg.endswith(self.base64_suffix):
                    break
            # reset radio state at end of each poll
            else:
                print("no received data, switching radio back to IDLE")
                await self.radio_state_semaphore.acquire()
                self.radio_state = 'IDLE'
                self.radio_state_semaphore.release()
        self.fl_client.text.clear_rx()
        # RX complete, reset radio state
        print("finishing receiving data, switching radio back to IDLE")
        await self.radio_state_semaphore.acquire()
        self.radio_state = 'IDLE'
        self.radio_state_semaphore.release()
        print("radio state IDLE, finishing parsing of received message")
        # check for correct prefix & suffix before sending
        msg_start = rx_msg.find(self.base64_prefix)
        msg_end = rx_msg.find(self.base64_suffix)
        if (msg_start == -1 or msg_end == -1):
            print("radio_receive invalid message!")
            print(rx_msg)
        else:
            return rx_msg[msg_start+len(self.base64_prefix):msg_end]

    async def radio_receive_test_task(self):
        while (True):
            print(await self.radio_receive())

    async def radio_receive_task(self, packet_deque: deque):
        print("started radio_receive_task")
        radio_buffer = bytes()
        while (True):
            radio_buffer = await self.radio_receive()
            print("Received:", radio_buffer)
            packet_deque.append(radio_buffer)

    def rig_info(self):
        print("bandwidth", self.fl_client.rig.bandwidth, "frequency", self.fl_client.rig.frequency,
              "mode", self.fl_client.rig.mode, "name", self.fl_client.rig.name)

    def rig_modify(self, bw='', freq=0.0, mode='', name=''):
        if (bw != None and bw != ''):
            self.fl_client.rig.bandwidth = bw
        if (freq != None and freq != 0.0):
            self.fl_client.rig.frequency = freq
        if (mode != None and mode != ''):
            self.fl_client.rig.mode = mode
        if (name != None and name != ''):
            self.fl_client.rig.name = name

    def modem_info(self):
        print("bandwidth", self.fl_client.modem.bandwidth, "carrier", self.fl_client.modem.carrier,
              "modem", self.fl_client.modem.name)

    def modem_modify(self, bw=0, carrier=0, modem=''):
        if (bw != None and bw != 0):
            self.fl_client.modem.bandwidth = bw
        if (carrier != None and carrier != 0):
            self.fl_client.modem.carrier = carrier
            self.fl_client.main.afc = False
        if (modem != None and modem != '' and self.fl_client.modem.names.count(modem) == 1):
            self.fl_client.modem.name = modem

    async def stop(self):
        self.fl_client.terminate(save_options=True)
        if (self.fl_app != None):
            trio.sleep(10.0)
            self.fl_app.kill()

# Convert raw data in a bytes() object to base64 for radio TX
def raw_to_base64(raw_bytes, prefix=fl_instance.base64_prefix):
    base64_buffer = codecs.encode(codecs.decode(raw_bytes.hex(), 'hex'), 'base64')
    # need to strip the newlines added every 76 bytes; intended for MIME
    # https://docs.python.org/3/library/base64.html#base64.encodebytes
    buffer_mod = len(base64_buffer) // 76
    stripped_buffer = base64_buffer.replace(b'\n', b'', buffer_mod)
    # add static prefix to assist with accurate decoding
    return (prefix + stripped_buffer)

# Convert base64-encoded RX radio data to raw bytes() object for port
def base64_to_raw(base64_bytes):
    return codecs.decode(base64_bytes, 'base64')

# use a timeout to detect the end of a message from a port
# increment the timer proportional to data received
# return data base64-encoded
async def port_receive(recv_port: trio.SocketStream, packet_deque: deque):
    print("calling port_receive")
    async for data in recv_port:
        print("port_received", data, "size", len(data))
        if (data == b''):
            print("input port closed, stopping port_receive")
            break
        else:
            packet_deque.append(raw_to_base64(data))
            print("packet queue:", packet_deque)

async def port_send(send_port: trio.SocketStream, packet_deque: deque):
    print("calling port_send")
    packet_buffer = bytes()
    poll_delay = 1.0
    while(True):
        if (len(packet_deque) > 0):
            packet_buffer = base64_to_raw(packet_deque.popleft())
            print("port_sending", packet_buffer, "size", len(packet_buffer))
            try:
                await send_port.send_all(packet_buffer)
            except Exception as exc:
                print("port_send failed; output port probably closed")
                print("{!r}".format(exc))
        else:
            await trio.sleep(poll_delay)

# Top-level wrappers to handle port->radio and radio->port
async def port_to_radio(fl_digi: fl_instance, proxy_port: trio.SocketStream):
    print("starting port_to_radio")
    packet_deque = deque()
    async with proxy_port:
        async with trio.open_nursery() as nursery:
            nursery.start_soon(port_receive, proxy_port, packet_deque)
            nursery.start_soon(fl_digi.radio_send_task, packet_deque)

async def radio_to_port(fl_digi: fl_instance, proxy_port: trio.SocketStream):
    print("starting radio_to_port")
    packet_deque = deque()
    async with proxy_port:
        async with trio.open_nursery() as nursery:
            nursery.start_soon(fl_digi.radio_receive_task, packet_deque)
            nursery.start_soon(port_send, proxy_port, packet_deque)

def test_standard():
    test_strings = ["TEST TEST TEST\n",
                    "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks.\n",
                    "The computer can be used as a tool to liberate and protect people, rather than to control them.\n"]
    return test_strings

def test_raw():
    # Lightning handshake messages captured from lnproxy
    test_handshake_0 = b'\x00\x03U\xc7\xaa\xa3\x85\xe8%\x95M\x96\xcbQ\x80C\x04\x0f\xf0\x14\xcf\x10\x11{t\x93=\x9d}\xa8a\xf5r\x02w\xca;\x11\xa1T\xaa\x81\xbf\xf2\xcbr\xd5;\xa9\xb2'
    test_handshake_1 = b'\x00\x02L\xdf\xd9\x81\x98\xcfr\xd8\xa7d\xd2\x167\x98\xff\x9b\t\x16\x1cR\x82^\x96\t8\xfb[\x9fv\x15d\n\xc0\xf7Wi\xf2\x1f\x9f\xd6ht\xba.\xf0>\\\x1c'
    test_handshake_2 = b'\x00\xae);;\xcd\x02\xea\x12A\xfc@\xb6L\xd6\xd2.\x8by\xfc\xddIR\xd9\x9e\x86\x96j\xbf\x8cA\xec\x8aD\xb0\xf1\xcb\xd6\xedQzq\xc3,\xb3W_\xf25\x0b\x066j\xd7\x06\xd3\xa0\xf0i=\xcd\xd8J\xb0\xffv'
    test_handshake_3 = b'\x00-\x00\x10\x00\x02"\x00\x00\x03\x02\xaa\xa2\x01 \x06"nF\x11\x1a\x0bY\xca\xaf\x12`C\xeb[\xbf(\xc3O:^3*\x1f\xc7\xb2\xb7<\xf1\x88\x91\x0f'
    handshakes = [test_handshake_0, test_handshake_1, test_handshake_2, test_handshake_3]
    handshakes_base64 = []
    hs_test = True
    for hs_message in handshakes:
        hs_base64 = raw_to_base64(hs_message, prefix=b'')
        print(hs_base64)
        # check for successful newline stripping
        if (hs_base64.count(b'\n') != 1):
            print("newline stripping failed!")
            hs_test = False
            break
        hs_raw = base64_to_raw(hs_base64)
        if (hs_raw != hs_message):
            print("encode/decode fail!")
            hs_test = False
            break
        else:
            handshakes_base64.append(hs_base64)
    if (hs_test == True):
        return handshakes_base64

async def connection_handler(proxy_stream, fl_main: fl_instance):
    async with trio.open_nursery() as nursery:
        nursery.start_soon(radio_to_port, fl_main, proxy_stream)
        nursery.start_soon(port_to_radio, fl_main, proxy_stream)

async def main():
    parser = argparse.ArgumentParser(description='Talk to fldigi.')
    parser.add_argument('--daemon', help="spawn a child fldigi process instead of attaching to one", action="store_true")
    parser.add_argument('--xml', type=int, help="XML-RPC port")
    parser.add_argument('--nohead', help='run fldigi without a GUI', action="store_true")
    parser.add_argument('--noproxy', help="run without TCP proxy functionality", action="store_true")
    parser.add_argument('--proxy_out', help="Set proxy port to outbound instead of inbound", action="store_true")
    parser.add_argument('--proxyport', type=int, help="TCP port for proxy")
    parser.add_argument('--carrier', type=int, help='set carrier frequency in Hz; disables AFC')
    parser.add_argument('--modem', type=str, help="select a specific modem")
    parser.add_argument('--rigmode', type=str, help="select a transceiver mode")
    args = parser.parse_args()
    print("args:", args.daemon, args.xml, args.nohead, args.noproxy, args.proxyport, args.carrier, args.modem, args.rigmode)
    # No default port when running as TCP proxy
    if (args.noproxy == False and args.proxyport == None):
        print("Need a proxy port!")
        return

    fl_main = fl_instance(daemon=args.daemon, noproxy=args.noproxy, xmlport=args.xml,
                          proxyport=args.proxyport, headless=args.nohead)
    print(fl_main.version())
    fl_main.port_info()
    fl_main.rig_info()
    fl_main.modem_info()
    if (args.rigmode != None):
        fl_main.rig_modify(mode=args.rigmode)
        print("transceiver mode now", args.rigmode)
    else:
        print("Defaulting to USB transceiver mode")
        fl_main.rig_modify(mode='USB')
    if (args.modem != None):
        fl_main.modem_modify(modem=args.modem)
        print("modem now", args.modem)
    else:
        print("Defaulting to PSK125R")
        fl_main.modem_modify(modem='PSK125R')
    if (fl_main.fl_client.modem.name in fl_main.modem_timeout_multipliers):
        fl_main.send_timeout_multiplier = fl_main.modem_timeout_multipliers[fl_main.fl_client.modem.name]
    else:
        print("No stored multiplier for how many seconds per byte your modem will do")
        print("Defaulting to multiplier for PSK125R")
        fl_main.send_timeout_multiplier = fl_main.modem_timeout_multipliers['PSK125R']
    if (args.carrier != None):
        fl_main.modem_modify(carrier=args.carrier)
        print("carrier frequency now", args.carrier, "Hz, AFC off")
    else:
        print("Defaulting to 1500 Hz carrier with AFC off")
        fl_main.modem_modify(carrier=1500)

    fl_main.clear_buffers()
    # TCP proxy mode
    if (args.noproxy == False):
        if (args.proxy_out == True):
            handler_wrapper = partial(connection_handler, fl_main=fl_main)
            try:
                await trio.serve_tcp(handler_wrapper, args.proxyport, host="127.0.0.1")
            except:
                print("Opening port for outbound proxy mode failed! Check port is not in use")
                return
        else:
            try:
                proxy_stream = await trio.open_tcp_stream("127.0.0.1", args.proxyport)
                async with proxy_stream:
                    await connection_handler(fl_main, proxy_stream)
            except:
                print("Opening port for inbound proxy mode failed! Check port is not in use")
                return

    else:
        # running instance started with custom config
        if (args.daemon):
            print("Attached to fldigi")
            if (args.noproxy == True):
                async with trio.open_nursery() as nursery:
                    nursery.start_soon(fl_main.radio_receive_test_task)
        # child of this script
        else:
            print("Started fldigi")
            if (args.noproxy == True):
                test_strings = test_standard()
                test_base64 = test_raw()
                async with trio.open_nursery() as nursery:
                    nursery.start_soon(fl_main.radio_send_test_task, test_strings)
                async with trio.open_nursery() as nursery:
                    nursery.start_soon(fl_main.radio_send_test_task, test_base64)
                fl_main.stop()


if __name__ == "__main__":
    trio.run(main)
