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
  * NOTE: On OS X, you may need to add a symlink for pyfldigi to find your fldigi installation, ex.
  * `sudo ln -s /Applications/fldigi-4.1.11.app/Contents/MacOS/fldigi /usr/local/bin`
* Initialize and use a venv for Python dependencies
* Use pip3 to install [pyfldigi](https://pythonhosted.org/pyfldigi/index.html) and [trio](https://trio.readthedocs.io/en/stable/)
  * NOTE: The pyfldigi docs are for 0.3, but the version provided by pip3 is 0.4
  * NOTE: If running on OS X, you'll need to remove the platform check in pyfldigi
    * Specifically on line 31 of appmonitor.py
* Make a directory which will be used to store fldigi config data

````bash
git clone https://github.com/jharveyb/fldigi-proxy.git
cd fldigi-proxy
sudo apt-get install python3.8 pavucontrol fldigi
python3.8 -m venv venv
source venv/bin/activate
pip3.8 install --upgrade pip
pip3.8 install -r requirements.txt
mkdir config_fldigi
````

### Fldigi initialization

* Start fldigi with config_fldigi the config_dir to initialize the configuration
  * Even though we don't use the fldigi ARQ interface, we need the two fldigi instances to not collide on those ports

`fldigi --config-dir config_fldigi`

* Skip the first page of the initial setup
* On the second page (Audio), select PulseAudio (or PortAudio if not on Linux); leave the server field empty if using PulseAudio
* Skip the remaining setup pages; fldigi should start, buts needs to be restarted to save the audio settings

### Audio loopback

#### Linux

* With fldigi running, open pavucontrol, and under the 'Recording' tab, set the fldigi process to capture from 'Monitor of $SINKNAME sink'
  * This means fldigi will listen on your default audio output instead of your microphone or other default source in PulseAudio.
  * PulseAudio settings are persistent, so all future fldigi instances should now use this 'audio loopback' setup.
* Test the audio loopback by playing some music - you should see output in the waterfall panel at the bottom of the fldigi GUI
  * In pavucontrol, the bars in the Playback and Recording tabs should be in sync

#### MacOS

* You should be able to set up an audio loopback when fldigi is using PortAudio
  * This [LOOPBACK](https://rogueamoeba.com/loopback/) program has been tested and successfully used
* Test the audio loopback by playing some music - you should see output in the waterfall panel at the bottom of the fldigi GUI

### Running fldigi-proxy

* fldigi-proxy will not run without any flags, and running in TCP proxy mode requires the proxy ports to be listening before start
* The relevant flags for running in TCP proxy mode are daemon, xml, proxyport, and proxy_out
  * by default, fldigi-proxy will attach to an fldigi instance with an XML-RPC interface open
    * fldigi-proxy can also start its own fldigi instance, but this uses the system config dir
  * proxy_out sets the mode for the proxy port between expecting an inbound or outbound connection
    * The default is to make an outbound connection; setting proxy_out means the proxy will expect to receive an outbound connection
  * The nohead, rigmode, carrier, modem settings can be set independently of the other flags that change proxy or test behavior

#### Examples

````bash
# Listen for an *inbound* connection on port 8822, attach to an fldigi instance listening on xml port 7362
# Radio settings are unspecified so default to transceiver mode = USB, carrier = 1500 Hz, modem = PSK125R
./fldigi_proxy.py --xml 7362 --proxy_out 8822

# Make an *outbound* connection to remote TCP port 2288, change some fldigi radio-specific settings on startup
./fldigi_proxy.py --xml 7362  --proxy_in 2288 --modem 'PSK125R' --rigmode 'CW' --carrier 1500
````

### TCP proxy test

NOTE: check which ports are already in use before assigning any here.

* Open a new terminal (Terminal 0) and start first fldigi

`fldigi --config-dir config_fldigi`

* Open a new terminal (Terminal 1) and start second fldigi

`fldigi --config-dir config_fldigi --arq-server-port 7323 --xmlrpc-server-port 7363`

* Open a new terminal (Terminal 2) and start the TCP test server
  * the test server sends four short binary packets captured from a node handshake in [lnproxy](https://github.com/willcl-ark/lnproxy/tree/2020-02-23-ham)

`./tcp_tester.py --auto`

* After a short delay, packets should start flowing from the test server to the sending proxy

* sent via fldigi to the listening proxy, and sent back to the test server, which checks that the packets match

* Upon success, you will note `Successful echo over proxy!` and `server finished` in the logs.

## Using with lnproxy

### Lnproxy setup

* Clone the [2020-02-23](https://github.com/willcl-ark/lnproxy/tree/2020-02-23-ham) branch of lnproxy
* Follow the setup instructions
* Start a 2 node lnproxy setup using:

```bash
# Source the helper scripts and start bitcoind/lightning nodes
source /path/to/lightning/contrib/startup_script_2.sh
start_ln
# Add the other node to each node's router
l1-cli add-node $(l2-cli gid) $(l2-cli getinfo | jq .id)
l2-cli add-node $(l1-cli gid) $(l1-cli getinfo | jq .id)
```

After you run `l2-cli add-node...` note the listening port connections from that node should connect in to.

### Fldigi setup

* Next we will start fldigi and fldigi-proxy using the config_fldigi dir created earlier in (#Install-dependencies)

```bash
cd /path/to/fldigi-proxy/
# Start two fldigi instances using based on that config
fldigi --config-dir config_fldigi
# (in a second terminal window)
fldigi --config-dir config_fldigi --arq-server-port 7323 --xmlrpc-server-port 7363
```

#### Checking settings (optional)

* You can check the settings for the two fldigi instances using the GUI if you choose:

* Check your soundcard is configured to use your loopback device, `Config > config dialogue > Soundcard > Devices`:

![soundcard_loopback](/assets/soundcard.png)

* Save and close the config dialogue. If you had to make any corrections, you need to restart,  `File > Exit` from the menu, to implement the changes.

* Again, save and quit second fldigi window if you had to make any changes.

* If you made changes, restart both fldigi instances again using the same commands as before:

```bash
# Start two fldigi instances
fldigi --config-dir config_fldigi
# (in a second terminal window)
fldigi --config-dir config_fldigi --arq-server-port 7323 --xmlrpc-server-port 7363
```

### Fldigi-proxy setup

* With 2x fldigi running, we can now connect fldigi-proxy to them. We need two more terminal windows for this:

```bash
cd /path/to/fldigi_proxy/

# In first window, this will connect to node1 who will make the outbound connection.
# --proxy_out is the port we listen on for this outbound connection from C-Lightning
./fldigi_proxy.py --xml 7362 --proxy_out 55555

# In second window. This will connect the inbound connection to C-Lightning
# YOU MUST change the --proxy_in port argument to match the value returned when you ran
# l2-cli add-node... command from Lnproxy Setup section above!
./fldigi_proxy.py --xml 7363 --proxy_in 99999
```

### Connecting together

* With 2 x fldigi + fldigi-proxy running, and two lightning nodes running with Lnproxy plugin enabled, we are ready to connect them together over the radio (ok, loopback soundcard device)!
* Back in the lnproxy window, where we previously sourced the lightning helper commands:

```bash
# NOTE: the tcp port here MUST match that used above in the "--proxy_out" parameter
l1-cli proxy-connect $(l2-cli gid) 55555

# Once the connection is complete
l1-cli fundchannel $(l2-cli getinfo | jq .id) 5000000 10000 false
bt-cli generatetoaddress 6 $(bt-cli getnewaddress "" bech32)

# ----
# Now we have a channel, we can make a payment
# ----

# To make a payment between two local nodes for testing, we can use the following to pass in an invoice, from node l2, to pay to:
l1-cli pay $(l2-cli invoice 500000 $(openssl rand -hex 12) $(openssl rand -hex 12) | jq -r '.bolt11')

# Otherwise we can use Lnproxy's (encrypted) `message` RPC command to send a "spontaneous send" style payment, where no invoice is required upfront:
l1-cli message $(l2-cli gid) $(openssl rand -hex 12) 100000
# or with custom encrypted message:
l1-cli message $(l2-cli gid) your_message_here 100000
```

* Complete

### Planned changes

* set default modem based on medium via flag, i.e. PSK500R for 'audio loopback', PSK125R for real radio
  * Calculate polling delays and other timeouts based on the modem baud rate
* add ARQ support to allow retransmit support
