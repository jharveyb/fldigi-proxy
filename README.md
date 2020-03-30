# Fldigi-proxy

Proxy between TCP/IP sockets (or raw text) and fldigi (HAM radio controller)

## Features

* Read and write from fldigi's RX & TX buffers
* Change basic modem settings
* Start an fldigi instance, or attach to a running instance

## Setup

* Install Python 3.7 (should also work with 3.8+ but not tested)
* Install fldigi (present in most distribution repos, or check <http://www.w1hkj.com/>)
* Use pip to install pyfldigi (<https://pythonhosted.org/pyfldigi/index.html>)
* NOTE: these docs are for 0.3, but the version provided by pip3 is 0.4 - some functions like main.send() have been removed
* For fldigi, the 'listenconfig' directory here matches the stock settings fldigi will return after the inital setup wizard; you can point flidigi to a specific config directory with 'fldigi --config-dir listenconfig'
* Set a custom XML-RPC port for an fldigi instance from the command line using --xmlrpc-server-port $PORTNUM
* You can also use --arq-server-port $PORTNUM to set the ARQ port, though that isn't used by this program
* To attach to a running fldigi instance, run ./kissproxy.py --nodaemon --xml=$PORTNUM
* If starting an fldigi instance using this script, run ./kissproxy.py (default XML-RPC port is 7362)
* To use a custom XML-RPC port when starting fldigi with this script, use the --xml=$PORTNUM argument
* You can also use the --nohead flag to run fldigi without a GUI
