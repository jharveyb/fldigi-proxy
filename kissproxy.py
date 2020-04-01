#!/usr/bin/python3.8

from time import sleep
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
            sleep(self.poll_delay)
            tx_confirm_fragment = self.fl_client.text.get_tx_data()
            if (tx_confirm_fragment != ''):
                if (tx_confirm_fragment.decode("utf-8") == '\n'):
                    break
                else:
                    tx_confirm_msg += tx_confirm_fragment.decode("utf-8")
        print("Sent!")
        sleep(self.poll_delay)
        self.fl_client.main.abort()
        self.fl_client.main.rx()

    async def radio_send_task(self, tx_msg_list):
        for tx_msg in tx_msg_list:
            await self.radio_send(tx_msg)

    # received content is raw bytes, newline-terminated
    async def radio_receive(self):
        rx_msg = bytes()
        rx_fragment = bytes()
        while (True):
            sleep(self.poll_delay)
            rx_fragment = self.fl_client.text.get_rx_data()
            #print(rx_fragment)
            if (rx_fragment != b''):
                if (rx_fragment == b'\n'):
                    break
                # not sure why we have to double check this
                elif (isinstance(rx_fragment, bytes)):
                    rx_msg += rx_fragment
        self.fl_client.text.clear_rx()
        return rx_msg

    async def radio_receive_task(self):
        while (True):
            print(await self.radio_receive())

    def modem_info(self):
        print("bandwidth", self.fl_client.rig.bandwidth, "frequency", self.fl_client.rig.frequency,
            "mode", self.fl_client.rig.mode, "name", self.fl_client.rig.name)

    def modem_modify(self, bw='', freq=0.0, mode='', name=''):
        if (bw != ''):
            self.fl_client.rig.bandwidth = bw
        if (freq != 0.0):
            self.fl_client.rig.frequency = freq
        if (mode != ''):
            self.fl_client.rig.mode = mode
        if (name != ''):
                self.fl_client.rig.name = name

    def stop(self):
        self.fl_client.terminate(save_options=True)
        sleep(self.stop_delay)
        self.fl_app.kill()

# Convert raw data in a bytes() object to base64 for radio TX
def raw_to_base64(raw_bytes):
    base64_buffer = codecs.encode(codecs.decode(raw_bytes.hex(), 'hex'), 'base64')
    # need to strip the newlines added every 76 bytes; intended for MIME
    # https://docs.python.org/3/library/base64.html#base64.encodebytes
    buffer_mod = len(base64_buffer) // 76
    return base64_buffer.replace(b'\n', b'', buffer_mod)

# Convert base64-encoded RX radio data to raw bytes() object for port 
def base64_to_raw(base64_bytes):
    return codecs.decode(base64_bytes, 'base64')

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
        hs_base64 = raw_to_base64(hs_message)
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
    parser.add_argument('--freq', type=float, help='set frequency in kHz')
    parser.add_argument('--noproxy', help="run without TCP proxy", action="store_true")
    parser.add_argument('--proxyport', type=int, help="TCP port of node to proxy; REQUIRED")
    args = parser.parse_args()
    print("args:", args.nodaemon, args.xml, args.nohead, args.freq, args.proxyport)
    # No default port when running as TCP proxy
    if (args.noproxy == False and args.proxyport == None):
        print("Need a proxy port!")
        return

    fl_main = fl_instance(nodaemon=args.nodaemon, noproxy=args.noproxy, xmlport=args.xml,
                            proxyport=args.proxyport, headless=args.nohead)
    print(fl_main.version())
    fl_main.port_info()
    sleep(fl_main.poll_delay)
    fl_main.modem_info()
    sleep(fl_main.poll_delay)
    if (args.freq != None):
        fl_main.modem_modify(freq=(args.freq*1e6))

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
                nursery.start_soon(fl_main.radio_send_task, test_strings)
            async with trio.open_nursery() as nursery:
                nursery.start_soon(fl_main.radio_send_task, test_base64)
            fl_main.stop()

if __name__ == "__main__":
    trio.run(main)