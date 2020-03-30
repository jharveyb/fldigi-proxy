# Fldigi-proxy

Proxy between TCP/IP sockets (or raw text) and fldigi (HAM radio controller)

## Features

* Read and write from fldigi's RX & TX buffers
* Change basic modem settings
* Start an fldigi instance, or attach to a running instance

## Setup (Tested only on Debian testing)

* Install Python 3.8 (should work on any python3 version but not tested)
* Install pavucontrol (to set sink & source for fldigi)
* Install fldigi (present in most distribution repos, or check <http://www.w1hkj.com/>)
* Use pip3 to install pyfldigi (<https://pythonhosted.org/pyfldigi/index.html>)
* NOTE: these docs are for 0.3, but the version provided by pip3 is 0.4 - some functions like main.send() have been removed
* For fldigi, the 'listenconfig' directory here matches the stock settings fldigi will return after the inital setup wizard; you can point flidigi to a specific config directory with 'fldigi --config-dir listenconfig'
* In fldigi, under Sound Card settings -> Devices, use 'PulseAudio' with an empty server string to test if you don't have a radio
* Start fldigi, open pavucontrol, and under the 'Recording' tab, set the fldigi process to capture from 'Monitor of $SINKNAME sink'; this means fldigi will read from your audio output instead of your microphone or default source in PulseAudio. This setting is saved by PulseAudio, so all future fldigi instances should now use the 'audio loopback' setup.
* You can test if the 'audio loopback' is configured correctly by playing some music - you should see output in the waterfall section of the fldigi GUI (panel at the bottom)
* Set a custom XML-RPC port for an fldigi instance from the command line using --xmlrpc-server-port $PORTNUM
* You can also use --arq-server-port $PORTNUM to set the ARQ port, though that isn't used by this program
* To attach to a running fldigi instance, run ./kissproxy.py --nodaemon --xml=$PORTNUM
* If starting an fldigi instance using this script, run ./kissproxy.py (default XML-RPC port is 7362)
* To use a custom XML-RPC port when starting fldigi with this script, use the --xml=$PORTNUM argument
* You can also use the --nohead flag to run fldigi without a GUI
