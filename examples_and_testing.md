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
