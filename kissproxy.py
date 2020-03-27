#!/usr/bin/python3.7

from time import sleep
import pyfldigi

# Test starting of fldigi, text encode/decode, and accepting messages to pass to fldigi
# over a TCP/IP socket

# default ports: 7322 for ARQ, 7342 for TCP/IP, 7362 for XML, 8421 for fllog

hostip = '127.0.0.1'
xmlport = 7362
tcpport = 7342
start_delay = 5
stop_delay = 3

flclient = pyfldigi.Client(hostname=hostip, port=xmlport)
flapp = pyfldigi.ApplicationMonitor(hostname=hostip, port=xmlport)

# ideally check if fldigi is already running with something ps -ef | grep fldigi flavored
# but we assume it isn't

flapp.start(headless=False, wfall_only=False)
sleep(start_delay)
print(flclient.version)
sleep(stop_delay)
# both terminate & stop ask for confirmation via pop-up, so need to force kill
flapp.kill()