# Fldigi-proxy

Proxy between TCP/IP sockets over fldigi (HAM radio controller)

## Features

* Read and write from fldigi's RX & TX buffers
* Change basic modem settings
* Start an fldigi instance, or attach to a running instance
* send raw binary data out over fldigi in base64 (and vice versa)

## Dependencies

* Python 3.8
* pavucontrol (or similar) and fldigi
* pyfldigi and trio

## Setup notes

### Install dependencies

* Install Python 3.8
* Install pavucontrol (to set sink & source for fldigi)
* Install [fldigi](http://www.w1hkj.com/) (present in most distribution repos)
* Initialize and use a venv for Python dependencies
* Use pip3 to install [pyfldigi](https://pythonhosted.org/pyfldigi/index.html) and [trio](https://trio.readthedocs.io/en/stable/)
  * NOTE: The pyfldigi docs are for 0.3, but the version provided by pip3 is 0.4
* Make a directory which will be used to store fldigi config data

````bash
git clone https://github.com/jharveyb/fldigi-proxy.git
cd fldigi-proxy
sudo apt-get install python3.8 pavucontrol fldigi
python3.8 -m venv venv
source venv/bin/activate
pip3.8 install --upgrade pip
pip3.8 install -r requirements.txt
mkdir fldigi_config
````

### Fldigi initialization

* Start fldigi with sender_config as the config_dir, and set the ARQ and XML-RPC ports
  * Even though we don't use the fldigi ARQ interface, we need the two fldigi instances to not collide on those ports

`fldigi --config-dir sender_config --arq-server-port 22446 --xmlrpc-server-port 44668`

* Skip the first page of the initial setup
* On the second page (Audio), select PulseAudio; leave the server field empty (or PortAudio if not on Linux)
  * If using PortAudio, you should check the 'Audio loopback' section
* Skip the last two pages; fldigi should start, buts needs to be restart to use the specified ports

### Audio loopback

* With fldigi running, open pavucontrol, and under the 'Recording' tab, set the fldigi process to capture from 'Monitor of $SINKNAME sink'
  * This means fldigi will listen on your default audio output instead of your microphone or other default source in PulseAudio.
  * PulseAudio settings are persistent, so all future fldigi instances should now use this 'audio loopback' setup.
  * If you are using PortAudio, you'll need to set up a capture device that returns the same audio as your playback device.
* Test the audio loopback by playing some music - you should see output in the waterfall panel at the bottom of the fldigi GUI
  * In pavucontrol, the bars in the Playback and Recording tabs should be in sync

### Running fldigi-proxy

* fldigi-proxy will not run without any flags, and run in TCP proxy mode requires the proxy ports to be listening before start
* The relevant flags for running in TCP proxy mode are nodaemon, xml, proxyport, and listener
  * nodaemon requires that we attach to a running fldigi instance, listening on the xml port we pass
    * fldigi-proxy starts its own fldigi instance by default; but we can't save settings to a specific directory in this case
      * However, if the system fldigi ports are unchanged, this will work
  * listener sets fldigi-proxy to pass data received on the radio to the TCP port passed with proxyport
    * The default mode is being a server, i.e. send data from a port over the radio
  * The nohead, carrier, and modem settings can be set regardless of which mode fldigi-proxy is run in

````python
# Run as a server for TCP proxy, accepting data on port 8822
./fldigi-proxy.py --proxyport 8822
# Attach to a running fldigi instance via XML-RPC port 44668
# and send data received via TCP proxy on port 8228
./fldigi-proxy.py --nodaemon --listener --xml 44668 --proxyport 8228
# Pass data received on port 8822 over the radio
# and additionally lock the carrier frequency to 1500 Hz
# (keeps sender & receiver from drifting given background noise)
# Use the BPSK63 modem instead of BPSK31 for lower latency
./fldigi-proxy.py --nodaemon --xml 22446 --proxyport 8822 --carrier 1500 --modem 'BPSK63'
````

### TCP proxy test

NOTE: check which ports are already in use before assigning any here; this test requires 6.

* Open a new terminal (Terminal 0) and start fldigi, which will be used for the proxy sender

`fldigi --config-dir sender_config --arq-server-port 22446 --xmlrpc-server-port 44668`

* Open a new terminal (Terminal 1) and start the test server
  * the test server sends four short binary packets captured from a node handshake in [lnproxy](https://github.com/willcl-ark/lnproxy/tree/2020-02-23-ham)

`./tcp_tester.py --inport 8822 --outport 2288`

* Open a new terminal (Terminal 2) and attach the listening proxy to the receiving fldigi instance

`./fldigi-proxy.py --nodaemon --xml 44668 --proxyport 2288 --listener --modem 'BPSK63' --carrier 1500`

* Open a new terminal (Terminal 3) and start the sending proxy

`./fldigi-proxy.py --proxyport 8822 --modem 'BPSK63' --carrier 1500`

* After a short delay, packets should start flowing from the test server to the sending proxy
* sent via fldigi to the listening proxy, and sent back to the test server, which checks that the packets match

#### Debug messages

* Terminal 3 shows packets being received, queued, and then converted to base64 and sent over fldigi
* Terminal 2 shows packets being received over fldigi, converted back to binary, and sent back out
* Terminal 1 shows the test server connecting to each end of the proxy, sending packets, and then receiving the packets

### Planned changes

* set default modem based on medium via flag, i.e. BPSK125+ for 'audio loopback', BPSK31 for real radio
  * Calculate polling delays and other timeouts based on the modem baud rate
* add either ARQ support or FEC wrapping for more reliable transmission
