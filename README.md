# Fldigi-proxy

Proxy between TCP/IP sockets and fldigi (HAM radio controller)

## Features

* Read and write from fldigi's RX & TX buffers
* Change basic modem settings
* Start an fldigi instance, or attach to a running instance

## Setup (Tested only on Debian testing)

* Install Python 3.8 (should work on any python3 version, but not tested)
* Install pavucontrol (to set sink & source for fldigi)
* Install [fldigi](http://www.w1hkj.com/) (present in most distribution repos)
* Use pip3 to install [pyfldigi](https://pythonhosted.org/pyfldigi/index.html) and [trio](https://trio.readthedocs.io/en/stable/)
  * NOTE: The pyfldigi docs are for 0.3, but the version provided by pip3 is 0.4 - some functions like main.send(), receive(), and transmit() have been removed
* For fldigi, the 'listenconfig' directory matches the stock settings fldigi will return after the inital setup wizard + port 9997 for KISS TCP/IP, port 9998 for XML-RPC, and port 9999 for ARQ
  * Point flidigi to a specific config directory with 'fldigi --config-dir $CONFIGDIR'
* In fldigi, under Configure -> Sound Card -> Devices, use PulseAudio with an empty server string to test if you don't have a radio i.e. via 'audio loopback'
* Start fldigi, open pavucontrol, and under the 'Recording' tab, set the fldigi process to capture from 'Monitor of $SINKNAME sink'
  * This means fldigi will listen on your default audio output instead of your microphone or default source in PulseAudio. This setting is saved by PulseAudio, so all future fldigi instances should now use this 'audio loopback' setup.
* Test if the 'audio loopback' is configured correctly by playing some music - you should see output in the waterfall panel at the bottom of the fldigi GUI
* Set a custom XML-RPC port for an fldigi instance from the command line using --xmlrpc-server-port $PORTNUM
  * Use --arq-server-port $PORTNUM to set the ARQ port (not currently used)
* The default fldigi XML-RPC port is 7362; use the --xml=$PORTNUM argument to provide an alternate port
  * The provided fldigi config will listen for XML-RPC commands on port 9998 by default
* To attach to a running fldigi instance, run ./kissproxy.py --nodaemon --xml=$PORTNUM
* To start fldigi from this script, run ./kissproxy.py
  * Use the --nohead flag to run fldigi without a GUI

### Detailed setup

* In one terminal (Terminal 0):

````bash
git clone https://github.com/jharveyb/fldigi-proxy.git
cd fldigi-proxy
sudo apt-get install python3.8 pavucontrol fldigi
pip3 install pyfldigi trio
fldigi
````

* On the top bar, click Configure -> Sound Card
* Select PulseAudio and close pop-up window

* Open a new terminal (Terminal 1) and run `pavucontrol`
* On the top bar, click Recording
* Change the field on the top right to 'Monitor of $SINKNAME sink'
* Play music or some audio file
* Observe fldigi and pavucontrol to confirm audio loopback
  * In fldigi, the bottom panel start out blank and then should scroll downwards with yellow and blue patterns
  * In pavucontrol, the bars in the Playback and Recording tabs should be in sync
* Close pavucontrol
* In Terminal 1, run `./kissproxy.py --nodaemon --xml=9998` to attach to the fldigi instance running in Terminal 0
* Open a new terminal (Terminal 2) and run `./kissproxy.py` to start another fldigi instance

### Planned changes

* add support for basic modem control
  * set default modem based on medium via flag, i.e. BPSK125+ for 'audio loopback', BPSK31 for real radio
* add either ARQ support or FEC wrapping for more reliable transmission
