import logging
import time
from collections import deque

import pyfldigi
import trio

logger = logging.getLogger("fldigi")
_client_logger = logging.getLogger("pyfldigi.client.text")
_client_logger.setLevel(logging.INFO)

class fl_instance:
    # default ports: 7322 for ARQ, 7342 for TCP/IP, 7362 for XML, 8421 for fllog
    host_ip = "127.0.0.1"
    xml_port = 7362
    proxy_port = 22
    poll_delay = 0.5
    base64_prefix = b"BTC"
    base64_suffix = b"\t\n"
    _time_per_byte = 0.25

    # we assume no port collisions for KISS, ARQ, or XMLRPC ports
    # TODO: check ports before starting
    def __init__(
        self,
        no_proxy=False,
        host=host_ip,
        xml_port=xml_port,
        proxy_in=None,
        proxy_out=None,
    ):
        self.host_ip = host
        if xml_port is not None:
            self.xml_port = xml_port
        if not no_proxy:
            self.proxy_in = proxy_in
            self.proxy_out = proxy_out
        self.fl_client = pyfldigi.Client(hostname=self.host_ip, port=self.xml_port)
        self.fl_app = pyfldigi.ApplicationMonitor(
            hostname=self.host_ip, port=self.xml_port
        )
        self.last_recv = time.time() - 25

    def port_info(self):
        logger.info(
            f"IP: {self.host_ip}\n"
            f"XML-RPC port: {self.xml_port}\n"
            f"proxy in: {self.proxy_in}\n"
            f"proxy out: {self.proxy_out}\n"

        )

    def version(self):
        return self.fl_client.version

    def clear_buffers(self):
        self.fl_client.text.clear_rx()
        self.fl_client.text.clear_tx()

    # send content manually vs. using main.send
    # assume we are in RX mode when calling (fldigi default state)
    # base64-encoded and newline-terminated
    # async def radio_send(self, tx_msg):
    #     # Clear send and recv text windows
    #     self.clear_buffers()
    #     # Query transmitted before starting to zero
    #     self.fl_client.text.get_tx_data()
    #     # Put into transmit mode
    #     self.fl_client.main.tx()
    #     # self.fl_client.text.transmit()
    #
    #     # Add the message to the Tx text widget
    #     self.fl_client.text.add_tx(tx_msg)
    #     logger.info(f"Sending: {tx_msg}")
    #
    #     # Magic number which should be enough transmit time for one message
    #     # because self.fl_client.get_tx_data() always returns null (on MacOS at least?)
    #     _sleep_dur = round(len(tx_msg) * self._time_per_byte, 3)
    #     logger.debug(f"Sleeping for {_sleep_dur}s whilst sending")
    #     await trio.sleep(_sleep_dur)
    #
    #     logger.info(f"Sent: {tx_msg}")
    #     await trio.sleep(self.poll_delay)
    #     self.fl_client.main.abort()
    #     self.fl_client.main.rx()

    async def radio_send_task(self, packet_deque: deque):
        logger.debug("started radio_send_task")
        while True:
            try:
                radio_buffer = packet_deque.popleft()
            # Nothing in the deque
            except IndexError:
                await trio.sleep(self.poll_delay)
            # Got something to send
            else:
                # First wait for a delay on last_recv time
                while self.last_recv + 25 > time.time():
                    await trio.sleep(self.poll_delay)
                logger.info(f"Sending: {radio_buffer}")
                _timeout = round(len(radio_buffer) * self._time_per_byte, 3)
                # We actually use a long timeout because we might be receiving which
                # blocks too
                self.fl_client.main.send(radio_buffer, True, 300)
                logger.info(f"Sent: {radio_buffer}")
                self.fl_client.main.abort()
                self.fl_client.main.rx()

    # received content is raw bytes, newline-terminated
    async def radio_receive(self):
        rx_msg = bytes()
        while True:
            await trio.sleep(self.poll_delay)
            # If we are transmitting, skip
            if self.fl_client.txmonitor.get_state() == "TX":
                continue
            # Strip any erroneous empty bytes
            rx_fragment = self.fl_client.text.get_rx_data().strip(b" ")
            # discard empty reads
            if rx_fragment is b"":
                continue
            else:
                logger.info(f"Got fragment: {rx_fragment}")
                self.last_recv = time.time()
                rx_msg += rx_fragment
                # This fragment marks the end of a message
                if rx_msg.endswith(b"\r\n"):
                    break
        self.fl_client.text.clear_rx()
        # Hack to strip prefix and suffix
        return rx_msg[len(self.base64_prefix):-len(self.base64_suffix)]

    async def radio_receive_task(self, packet_deque: deque):
        logger.debug("started radio_receive_task")
        while True:
            radio_buffer = await self.radio_receive()
            logger.info(f"Received: {radio_buffer}")
            packet_deque.append(radio_buffer)

    def rig_info(self):
        logger.info(
            f"bandwidth: {self.fl_client.rig.bandwidth}\n"
            f"frequency: {self.fl_client.rig.frequency}\n"
            f"mode: {self.fl_client.rig.mode}\n"
            f"name: {self.fl_client.rig.name}\n"
        )

    def rig_modify(self, bw="", freq=0.0, mode="", name=""):
        if bw is not None and bw != "":
            self.fl_client.rig.bandwidth = bw
        if freq is not None and freq != 0.0:
            self.fl_client.rig.frequency = freq
        if mode is not None and mode != "":
            self.fl_client.rig.mode = mode
        if name is not None and name != "":
            self.fl_client.rig.name = name

    def modem_info(self):
        logger.info(
            f"bandwidth {self.fl_client.modem.bandwidth}\n"
            f"carrier {self.fl_client.modem.carrier}\n"
            f"modem {self.fl_client.modem.name}\n"
        )

    def modem_modify(self, bw=0, carrier=0, modem=""):
        if bw is not None and bw != 0:
            self.fl_client.modem.bandwidth = bw
        if carrier is not None and carrier != 0:
            self.fl_client.modem.carrier = carrier
            self.fl_client.main.afc = False
        if (
            modem is not None
            and modem != ""
            and self.fl_client.modem.names.count(modem) == 1
        ):
            if modem[0:4] == "BPSK":
                self.fl_client.modem.name = modem

    def stop(self):
        self.fl_client.terminate(save_options=True)
        time.sleep(1)
        self.fl_app.kill()
