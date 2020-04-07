#!/usr/bin/env python
import logging
from collections import deque
from functools import partial

import trio

import util
from _fldigi import fl_instance

POLL_DELAY = 1.0

# Setup logging
logging.basicConfig(
    level=logging.DEBUG, format="%(name)-12s: %(levelname)-8s %(message)s"
)
logger = logging.getLogger("proxy")
# Turn down this noisy logger
urllib = logging.getLogger("urllib3.connectionpool")
urllib.setLevel(logging.INFO)


# use a timeout to detect the end of a message from a port
# increment the timer proportional to data received
# return data base64-encoded
async def port_receive(recv_port: trio.SocketStream, packet_deque: deque):
    logger.info("calling port_receive")
    while True:
        data = await recv_port.receive_some(max_bytes=1024)
        if not data:
            await trio.sleep(POLL_DELAY)
            continue
        if data == b" " or b"":
            await trio.sleep(POLL_DELAY)
            continue
        logger.info(f"port_received: {data}")
        packet_deque.append(util.raw_to_base64(data))
        logger.debug(f"packet queue: {packet_deque}")


async def port_send(send_port: trio.SocketStream, packet_deque: deque):
    logger.debug("calling port_send")
    while True:
        if len(packet_deque) > 0:
            packet_buffer = util.base64_to_raw(packet_deque.popleft())
            logger.info(f"port_sending {packet_buffer}")
            await send_port.send_all(packet_buffer)
        else:
            await trio.sleep(POLL_DELAY)


async def port_to_radio(fl_digi: fl_instance, proxy_port: trio.SocketStream):
    logger.debug("Starting port_to_radio")
    packet_deque = deque()
    async with proxy_port:
        async with trio.open_nursery() as nursery:
            nursery.start_soon(port_receive, proxy_port, packet_deque)
            nursery.start_soon(fl_digi.radio_send_task, packet_deque)


async def radio_to_port(fl_digi: fl_instance, proxy_port: trio.SocketStream):
    logger.debug("Starting radio_to_port")
    packet_deque = deque()
    async with proxy_port:
        async with trio.open_nursery() as nursery:
            nursery.start_soon(fl_digi.radio_receive_task, packet_deque)
            nursery.start_soon(port_send, proxy_port, packet_deque)


async def handle_conn(stream, fl_main):
    logger.info("Handling new connection")
    async with trio.open_nursery() as nursery:
        nursery.start_soon(port_to_radio, fl_main, stream)
        nursery.start_soon(radio_to_port, fl_main, stream)


async def main():
    args = util.parse_args()

    fl_main = fl_instance(
        no_proxy=args.noproxy,
        xml_port=args.xml,
        proxy_in=args.proxy_in,
        proxy_out=args.proxy_out,
    )
    util.print_fl_stats(fl_main, args)

    ####################################################################################
    # TCP proxy mode
    ####################################################################################

    # C-Lightning is going to make a new _outbound_ connection to a remote node via the
    # radio. We listen on args.proxy_in
    if args.proxy_out:
        # Use functools.partial to pass fl_main into the handler
        _handle_func = partial(handle_conn, fl_main=fl_main)
        await trio.serve_tcp(_handle_func, int(args.proxy_out), host="127.0.0.1")

    # We are receiving a connection from a remote node, so we make an inbound connection
    # to lnproxy
    if args.proxy_in:
        proxy_stream = await trio.open_tcp_stream("127.0.0.1", args.proxy_in)
        async with proxy_stream:
            await handle_conn(proxy_stream, fl_main)


if __name__ == "__main__":
    trio.run(main)
