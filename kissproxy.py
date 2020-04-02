#!/usr/bin/python3.8

from time import sleep
from collections import deque
import argparse
import pyfldigi
import codecs
import trio

# Test starting of fldigi, text encode/decode, and accepting messages to pass to fldigi
# over a TCP/IP socket

# default ports: 7322 for ARQ, 7342 for TCP/IP, 7362 for XML, 8421 for fllog

class fl_instance:
    host_ip = '127.0.0.1'
    xml_port = 7362
    proxy_port = 22
    start_delay = 5
    stop_delay = 3
    poll_delay = 0.05
    base64_prefix = b'BTC'

    # we assume no port collisions for KISS, ARQ, or XMLRPC ports
    # TODO: check ports before starting
    def __init__(self, nodaemon=False, noproxy=False, host=host_ip, xmlport=xml_port,
        proxyport=proxy_port, headless=False, wfall_only=False, start_delay=start_delay):
        self.host_ip = host
        if (xmlport != None):
            self.xml_port = xmlport
        if (noproxy == False):
            self.proxy_port = proxyport
        self.start_delay = start_delay
        self.fl_client = pyfldigi.Client(hostname=self.host_ip, port=self.xml_port)
        self.fl_app = pyfldigi.ApplicationMonitor(hostname=self.host_ip, port=self.xml_port)
        if (nodaemon == False):
            self.fl_app.start(headless=headless, wfall_only=wfall_only)
        sleep(self.start_delay)

    def port_info(self):
        print("IP", self.host_ip, "XML-RPC port:", self.xml_port, "proxy port:", self.proxy_port)

    def version(self):
        return self.fl_client.version

    def clear_buffers(self):
        self.fl_client.text.clear_rx()
        self.fl_client.text.clear_tx()

    # send content manually vs. using main.send
    # assume we are in RX mode when calling (fldigi default state)
    # base64-encoded and newline-terminated
    async def radio_send(self, tx_msg):
        self.fl_client.text.clear_rx()
        self.fl_client.text.clear_tx()
        self.fl_client.main.tx()
        self.fl_client.text.add_tx(tx_msg)
        # Poll and check TX'd data; reassemble & end send once msg made it out
        byteflag = isinstance(tx_msg, bytes)
        tx_confirm_msg = ''
        tx_confirm_fragment = []
        print("Sending:", tx_msg)
        while (tx_msg != tx_confirm_msg):
            await trio.sleep(self.poll_delay)
            tx_confirm_fragment = self.fl_client.text.get_tx_data()
            if (tx_confirm_fragment != ''):
                if (tx_confirm_fragment.decode("utf-8") == '\n'):
                    break
                else:
                    tx_confirm_msg += tx_confirm_fragment.decode("utf-8")
        print("Sent!")
        await trio.sleep(self.poll_delay)
        self.fl_client.main.abort()
        self.fl_client.main.rx()

    async def radio_send_test_task(self, tx_msg_list):
        for tx_msg in tx_msg_list:
            await self.radio_send(tx_msg)

    async def radio_send_task(self, packet_deque: deque): 
        print("started radio_send_task")
        radio_buffer = bytes()
        while(True):
            if (len(packet_deque) > 0):
                radio_buffer = packet_deque.popleft()
                await self.radio_send(radio_buffer)
            else:
                await trio.sleep(self.poll_delay)

    # received content is raw bytes, newline-terminated
    async def radio_receive(self):
        rx_msg = bytes()
        rx_prefix = bytes()
        rx_prefix_check = False
        rx_fragment = bytes()
        while (True):
            await trio.sleep(self.poll_delay)
            rx_fragment = self.fl_client.text.get_rx_data()
            # empty reads are strings, not bytes
            if (isinstance(rx_fragment, bytes) and rx_fragment != b''):
                if (rx_prefix_check == False):
                    rx_prefix += rx_fragment
                    if (rx_prefix.endswith(self.base64_prefix)):
                        rx_prefix_check = True
                # all data before prefix excluded from message, including noise from keying up radio
                else: 
                    if (rx_fragment == b'\n'):
                        break
                    elif (rx_fragment == b'\r'):
                        pass
                    else:
                        rx_msg += rx_fragment
        self.fl_client.text.clear_rx()
        return rx_msg

    async def radio_receive_test_task(self):
        while (True):
            print(await self.radio_receive())

    async def radio_receive_task(self, packet_deque: deque):
        print("started radio_receive_task")
        radio_buffer = bytes()
        while (True):
            radio_buffer = await self.radio_receive()
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
            if (modem[0:4] == 'BPSK'):
                self.fl_client.modem.name = modem

    def stop(self):
        self.fl_client.terminate(save_options=True)
        sleep(self.stop_delay)
        self.fl_app.kill()

# Convert raw data in a bytes() object to base64 for radio TX
def raw_to_base64(raw_bytes, prefix=b'BTC'):
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
        print("port_received", data)
        if (data != b''):
            print("port_receive length", len(data))
            packet_deque.append(raw_to_base64(data))
            print(packet_deque)

async def port_send(send_port: trio.SocketStream, packet_deque: deque):
    print("calling port_send")
    packet_buffer = bytes()
    poll_delay = 1.0
    while(True):
        if (len(packet_deque) > 0):
            packet_buffer = base64_to_raw(packet_deque.popleft())
            await send_port.send_all(packet_buffer)
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

async def main():
    parser = argparse.ArgumentParser(description='Talk to fldigi.')
    parser.add_argument('--nodaemon', help="attach to an fldigi process", action="store_true")
    parser.add_argument('--xml', type=int, help="XML port")
    parser.add_argument('--nohead', help='run fldigi headless', action="store_true")
    parser.add_argument('--noproxy', help="run without TCP proxy", action="store_true")
    parser.add_argument('--proxyport', type=int, help="TCP port of node to proxy; REQUIRED")
    parser.add_argument('--carrier', type=int, help='set carrier frequency in Hz; disables AFC')
    parser.add_argument('--modem', type=str, help="select a specific modem")
    args = parser.parse_args()
    print("args:", args.nodaemon, args.xml, args.nohead, args.proxyport, args.carrier, args.modem)
    # No default port when running as TCP proxy
    if (args.noproxy == False and args.proxyport == None):
        print("Need a proxy port!")
        return

    fl_main = fl_instance(nodaemon=args.nodaemon, noproxy=args.noproxy, xmlport=args.xml,
                            proxyport=args.proxyport, headless=args.nohead)
    print(fl_main.version())
    fl_main.port_info()
    sleep(fl_main.poll_delay)
    fl_main.rig_info()
    sleep(fl_main.poll_delay)
    fl_main.modem_info()
    sleep(fl_main.poll_delay)
    fl_main.modem_modify(modem=args.modem, carrier=args.carrier)
    if (args.modem != None):
        print("modem now", args.modem)
    if (args.carrier != None):
        print("carrier frequency now", args.carrier, "Hz, AFC off")

    # running instance started with custom config
    if (args.nodaemon):
        print("Attached to fldigi")
        if (args.noproxy == True):
            fl_main.clear_buffers()
            async with trio.open_nursery() as nursery:
                nursery.start_soon(fl_main.radio_receive_task)
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

    # TCP proxy mode
    if (args.noproxy == False):
        # TODO: pick role as either listener or server
        # trio stream type needs to change + only one of port-to-radio or radio-to-port
        proxy_stream = await trio.open_tcp_stream("127.0.0.1", args.proxyport)

        async with proxy_stream:
            async with trio.open_nursery() as nursery:
                nursery.start_soon(port_to_radio, fl_main, proxy_stream)
                nursery.start_soon(radio_to_port, fl_main, proxy_stream)

if __name__ == "__main__":
    trio.run(main)