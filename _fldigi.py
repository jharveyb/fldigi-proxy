import logging
import time
from collections import deque
from random import randint

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
    # Mirror poll delay from pyfldigi.Client.TxMonitor
    poll_delay = 0.25
    base64_prefix = b"BTC"
    base64_suffix = b"\t\n"

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
        self.last_recv = time.time()
        self.last_send = time.time()

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
                # Some sleeps to try and avoid transmitting at same time
                # If last receive a while ago, random wait before sending
                if self.last_recv + 20 < time.time():
                    delay = randint(1, 20)
                    logger.debug(
                        f"Last receive a while ago, waiting {delay}s as random offset."
                    )
                    await trio.sleep(randint(1, 20))
                # If we last send, sleep longer to be polite
                delay = 10 if self.last_send > self.last_recv else 5
                logger.debug(f"We sent last! Waiting {delay}s to permit response")
                while self.last_recv + delay > time.time():
                    await trio.sleep(self.poll_delay)

                logger.info(f"Sending: {radio_buffer}")
                # We actually use a long timeout because we might be receiving which
                # blocks too
                try:
                    self.fl_client.main.send(radio_buffer, True, 300)
                except TimeoutError as e:
                    # Try to continue
                    logger.exception(e)
                logger.info(f"Sent: {radio_buffer}")
                self.fl_client.main.abort()
                self.fl_client.main.rx()

    async def get_fragment(self):
        await trio.sleep(self.poll_delay)
        fragment = self.fl_client.text.get_rx_data().strip(b" ")
        if fragment is not b"":
            logger.info(f"Got fragment: {fragment}")
            self.last_recv = time.time()
        return fragment

    # received content is raw bytes, newline-terminated
    async def radio_receive(self):
        rx_msg = bytes()
        rx_msg += await self.get_fragment()
        # Didn't get anything
        if rx_msg is b"":
            return rx_msg
        else:
            while True:
                rx_msg += await self.get_fragment()
                # This fragment marks the end of a message
                if rx_msg.endswith(b"\r\n"):
                    break
        self.fl_client.text.clear_rx()
        # Hack to strip prefix and suffix
        return rx_msg[len(self.base64_prefix) : -len(self.base64_suffix)]

    async def radio_receive_task(self, packet_deque: deque):
        logger.debug("started radio_receive_task")
        while True:
            await trio.sleep(self.poll_delay)
            radio_buffer = await self.radio_receive()
            if radio_buffer:
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
