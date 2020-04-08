#!/usr/bin/env python

"""
Test proxying between two fldigi & fldigi-proxy instances
by passing binary data bidirectionally
"""

import argparse
import logging
import subprocess

import trio

test_handshake_0 = b"\x00\x03U\xc7\xaa\xa3\x85\xe8%\x95M\x96\xcbQ\x80C\x04\x0f\xf0\x14\xcf\x10\x11{t\x93=\x9d}\xa8a\xf5r\x02w\xca;\x11\xa1T\xaa\x81\xbf\xf2\xcbr\xd5;\xa9\xb2"
test_handshake_1 = b"\x00\x02L\xdf\xd9\x81\x98\xcfr\xd8\xa7d\xd2\x167\x98\xff\x9b\t\x16\x1cR\x82^\x96\t8\xfb[\x9fv\x15d\n\xc0\xf7Wi\xf2\x1f\x9f\xd6ht\xba.\xf0>\\\x1c"
test_handshake_2 = b"\x00\xae);;\xcd\x02\xea\x12A\xfc@\xb6L\xd6\xd2.\x8by\xfc\xddIR\xd9\x9e\x86\x96j\xbf\x8cA\xec\x8aD\xb0\xf1\xcb\xd6\xedQzq\xc3,\xb3W_\xf25\x0b\x066j\xd7\x06\xd3\xa0\xf0i=\xcd\xd8J\xb0\xffv"
test_handshake_3 = b'\x00-\x00\x10\x00\x02"\x00\x00\x03\x02\xaa\xa2\x01 \x06"nF\x11\x1a\x0bY\xca\xaf\x12`C\xeb[\xbf(\xc3O:^3*\x1f\xc7\xb2\xb7<\xf1\x88\x91\x0f'
handshakes = [test_handshake_0, test_handshake_1, test_handshake_2, test_handshake_3]


async def recv_echo(proxy_port):
    try:
        async for data in proxy_port:
            print("receiving echoed data:", data)
            return data
    except Exception as exc:
        print("receive_echo crashed: {!r}".format(exc))


async def send_raw_recv_echo(proxy_port, packets, echo=False):
    echoed_data = []
    packet_counter = 0
    listen_echoes = True
    valid_echo = True
    print("Beginning to serve raw packets, echo =", echo)
    for data in packets:
        print("sending data:", data)
        await proxy_port.send_all(data)
        # packet will queue in proxy
        await trio.sleep(1.5)
    # receive echoes
    if echo:
        print("Waiting for echoes")
        while listen_echoes:
            echoed_packet = await recv_echo(proxy_port)
            if echoed_packet != packets[packet_counter]:
                print("Echoed packet doesn't match sent packet!")
                valid_echo = False
            echoed_data.append(echoed_packet)
            packet_counter += 1
            if packet_counter == len(packets):
                print("received correct number of echoed packets")
                listen_echoes = False
            await trio.sleep(0.5)
        print("checking echoed data")
        if len(echoed_data) == len(packets) and (valid_echo == True):
            print("Successful echo over proxy!")


async def tester_client(output_stream):
    print("fldigi output client started")
    received_data = []
    received_counter = 0
    try:
        async for data in output_stream:
            print("receiving data:", data)
            received_data.append(data)
            received_counter += 1
            if received_counter == len(handshakes):
                break
    except Exception as exc:
        print("tester client crashed: {!r}".format(exc))
    print("client finished receiving data")
    # delay for radio to switch from RX to TX
    await trio.sleep(3.0)
    print("echoing received data")
    for data in received_data:
        print("echoing:", data)
        await output_stream.send_all(data)
        # wait for each packet to go out
        await trio.sleep(15.0)
    await trio.sleep(1.0)
    print("client finished")
    return


async def tester_server(input_stream):
    print("fldigi input server started")
    try:
        await trio.sleep(1.0)
        await send_raw_recv_echo(input_stream, handshakes, echo=True)
        print("server finished")
        return
    except Exception as exc:
        print("tester server crashed: {!r}".format(exc))


async def server_wrapper(inport):
    print("wrapping server")
    await trio.serve_tcp(tester_server, inport)


async def client_wrapper(outport):
    print("wrapping client")
    # await tester_client(await trio.open_tcp_stream("localhost", outport))
    await trio.serve_tcp(tester_client, outport)


async def main():
    # fmt: off
    parser = argparse.ArgumentParser(description="test fldigi-proxy")
    parser.add_argument("--inport", type=int, default=8822, help="input port for fldigi-proxy")
    parser.add_argument("--outport", type=int, default=2288, help="output port for fldigi-proxy")
    parser.add_argument("--auto", default=False, help="Add debug output", action="store_true")
    parser.add_argument("--debug", default=False, help="Add debug output", action="store_true")
    # fmt: on
    args = parser.parse_args()
    if not args.debug:
        logging.getLogger("fldigi").setLevel(logging.INFO)
        logging.getLogger("proxy").setLevel(logging.INFO)
        logging.getLogger("pyfldigi.client.txmonitor").setLevel(logging.INFO)

    if args.auto:
        print(
            "Ensure two instances of fldigi are running with :\n"
            "1: --xmlrpc-server-port 7362\n"
            "2: --xmlrpc-server-port 7363"
        )
    print("TCP tester started")

    async with trio.open_nursery() as nursery:
        nursery.start_soon(server_wrapper, args.inport)
        nursery.start_soon(client_wrapper, args.outport)
        if args.auto:
            await trio.sleep(0.1)
            nursery.start_soon(
                trio.to_thread.run_sync,
                subprocess.call,
                [
                    "python",
                    "fldigi_proxy.py",
                    "--xml",
                    "7362",
                    "--modem",
                    "PSK125R",
                    "--carrier",
                    "1500",
                    "--proxy_in",
                    "8822",
                ],
            )
            nursery.start_soon(
                trio.to_thread.run_sync,
                subprocess.call,
                [
                    "python",
                    "fldigi_proxy.py",
                    "--xml",
                    "7363",
                    "--modem",
                    "PSK125R",
                    "--carrier",
                    "1500",
                    "--proxy_in",
                    "2288",
                ],
            )


if __name__ == "__main__":
    trio.run(main)
