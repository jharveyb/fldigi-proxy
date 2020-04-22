# Fldigi-proxy

Proxy between TCP/IP sockets over fldigi (HAM radio controller)

## Features

* Read and write from fldigi's RX & TX buffers
* Change basic modem settings
* Start an fldigi instance, or attach to a running instance
* send raw binary data out over fldigi in base64 (and vice versa)

## Dependencies

* Python >= 3.7
* pavucontrol (or similar) and fldigi
* pyfldigi and trio

## Setup notes

### Install dependencies

* Install Python => 3.7

Check NOTEs below install instructions

````bash
# MacOS: install fldigi manually from http://www.w1hkj.com/
sudo apt install pavucontrol fldigi # Unix only

# Clone this repo
git clone https://github.com/jharveyb/fldigi-proxy.git
cd fldigi-proxy
git checkout sync-timer

# Initialize and use a venv for Python dependencies
python3 -m venv venv
source venv/bin/activate

# Install python dependencies
pip3 install --upgrade pip
pip3 install -r requirements.txt

# Make a directory which will be used to store fldigi config data
mkdir config_fldigi
````

* NOTE: On MacOS, you may need to add a symlink for pyfldigi to find your fldigi installation, ex:
  * `sudo ln -s /Applications/fldigi-4.1.11.app/Contents/MacOS/fldigi /usr/local/bin`

* NOTE: The pyfldigi docs are for 0.3, but the version provided by pip3 is 0.4

* NOTE: If on MacOS and you *don't* install pyfldigi from requirements.txt (which uses a patched version), you'll need to remove the platform check in pyfldigi on line 31 of appmonitor.py

### Fldigi initialization

* Start fldigi with --config-dir flag to initialize the configuration

```bash
fldigi --config-dir config_fldigi
```


* Skip the first page of the initial setup
* On the second page (Audio), select PulseAudio (or PortAudio if not on Linux); leave the server field empty if using PulseAudio
* Skip the remaining setup pages
* fldigi should start, *but needs to be restarted once* to save the audio device settings

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


## Using with lnproxy; single node; testnet (default)

### Lnproxy setup

* Follow the install instructions to install [Lnproxy](https://github.com/willcl-ark/lnproxy) including cloning and compiling the custom C-Lightning branch with patches and configured using the `--enable-developer` flag.


```bash
# From the c-lightning source directory as cloned above, source the helper scripts
source contrib/startup_testnet1.sh

# Start C-Lightning
start_ln
```

Here the instructions diverge depending on who will make the _outbound_ connection. We will use terms:

* Outbound (initiating connection)
* Inbound (receiving connection)

The initiator should follow the section immediately below [Outbound](#outbound), and the receiver should skip to the [Inbound](#inbound) section below:

### Outbound

Let's export an environment variable to help us later:

```bash
export FLD_PORT=55555
```

We can add the remote node to the Lnproxy router. The final `11111` (listening port) is not important for "A" because it will make outbound connection, but a valid port number is still required here:

```bash
l1-cli add-node <remote_pubkey>@127.0.0.1:$FLD_PORT 11111
```

Let's start main `fldigi` and also `fldigi-proxy` listening on a port ready for us:

```bash
# To start fldigi main app:
cd /path/to/fldigi-proxy/
# Start fldigi instances using based on that config
fldigi --config-dir config_fldigi

# Now in a new terminal window start fldigi-proxy:
cd /path/to/fldigi-proxy/
./fldigi_proxy.py --xml 7362 --proxy_out $FLD_PORT
```

When you have confirmation that your counter-party, "B" is also setup with fldigi, _you_ can begin the connecting sequence:

```bash
l1-cli proxy-connect <remote_pubkey>

# Once connected, you can follow additional C-Lightning/Lnproxy commands, e.g.:
l1-cli fundchannel <remote_pubkey> 1000000 10000 false

# To pay an invoice first acquire an invoice out of band, then:
l1-cli pay <bolt11_invoice>

# We can use Lnproxy's (encrypted) `message` RPC command to send a "spontaneous send" style payment, where no invoice is required upfront:
l1-cli message <remote_pubkey> your_message_here <amount_msat>
```

### Inbound

B is receiving the inbound connection. Let's export an environment variable:

```bash
export FLD_PORT=22222
```

We can add the remote node to the Lnproxy router. The port `22222` (listening port of A) is not important for "B" because it will make receive inbound connection on $FLD_PORT, but a valid port number is still required:

```bash
l1-cli add-node <remote_pubkey>@127.0.0.1:22222 $FLD_PORT
```

Let's start main `fldigi` and also `fldigi-proxy` and tell fldigi-proxy which port to proxy to when it receives a signal from fldigi:

```bash
# To start fldigi main app:
cd /path/to/fldigi-proxy/
# Start fldigi based on that config
fldigi --config-dir config_fldigi

# Now in a new terminal window
cd /path/to/fldigi-proxy/
./fldigi_proxy.py --xml 7362 --proxy_in $FLD_PORT
```

Wait for incoming connection from the radio


### Planned changes

* set default modem based on medium via flag, i.e. PSK500R for 'audio loopback', PSK125R for real radio
  * Calculate polling delays and other timeouts based on the modem baud rate
* add ARQ support to allow retransmit support
