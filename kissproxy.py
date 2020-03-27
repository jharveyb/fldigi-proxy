#!/usr/bin/python3.7

from time import sleep
import pyfldigi

# Test starting of fldigi, text encode/decode, and accepting messages to pass to fldigi
# over a TCP/IP socket

# default ports: 7322 for ARQ, 7342 for TCP/IP, 7362 for XML, 8421 for fllog

class fl_instance:
    host_ip = '127.0.0.1'
    xml_port = 7362
    tcp_port = 7342
    start_delay = 5
    stop_delay = 3
    poll_delay = 0.1

    # we assume no port collisions / no other instance of fldigi is running
    # TODO: check for other fldigi instances before starting
    def __init__(self, host=host_ip, port=xml_port, headless=False, wfall_only=False, start_delay=start_delay):
        self.host_ip = host
        self.xml_port = port
        self.start_delay = start_delay
        self.fl_client = pyfldigi.Client(hostname=self.host_ip, port=self.xml_port)
        self.fl_app = pyfldigi.ApplicationMonitor(hostname=self.host_ip, port=self.xml_port)
        self.fl_app.start(headless=headless, wfall_only=wfall_only)
        sleep(self.start_delay)

    def port_info(self):
        print("IP", self.host_ip, "XML-RPC port:", self.xml_port, "TCP port:", self.tcp_port)

    def version(self):
        return self.fl_client.version

    # send content manually vs. using main.send; assume we are in RX mode when calling
    def send(self, tx_msg=[]):
        self.fl_client.text.clear_tx()
        self.fl_client.main.tx()
        self.fl_client.text.add_tx(tx_msg)
        # Poll and check TX'd data; reassemble & end send once msg made it out
        tx_confirm_msg = ''
        tx_confirm_fragment = []
        print("Sending:", tx_msg)
        while (tx_msg != tx_confirm_msg):
            sleep(self.poll_delay)
            tx_confirm_fragment = self.fl_client.text.get_tx_data()
            if (tx_confirm_fragment != ''):
                # special strings
                if (tx_confirm_fragment.decode("utf-8") == '\n'):
                    break
                else:
                    tx_confirm_msg += tx_confirm_fragment.decode("utf-8")
        self.fl_client.main.abort()
        self.fl_client.main.rx()

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

test_strings = ["TEST TEST TEST", "\n", "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks.", 
    "\n", "The computer can be used as a tool to liberate and protect people, rather than to control them.", "\n"]

fl_main = fl_instance()
print(fl_main.version())
fl_main.port_info()
fl_main.stop()