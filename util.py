"""
Global utilities for data encode/decode + tests for fldigi-proxy <-> fldigi interface
"""

import argparse
import codecs

# Convert raw data in a bytes() object to base64 for radio TX
def raw_to_base64(raw_bytes, prefix=b"BTC"):
    base64_buffer = codecs.encode(codecs.decode(raw_bytes.hex(), "hex"), "base64")
    # need to strip the newlines added every 76 bytes; intended for MIME
    # https://docs.python.org/3/library/base64.html#base64.encodebytes
    stripped_buffer = base64_buffer.replace(b"\n", b"")
    # add static prefix to assist with accurate decoding
    return prefix + stripped_buffer + b"\n"


# Convert base64-encoded RX radio data to raw bytes() object for port
def base64_to_raw(base64_bytes):
    return codecs.decode(base64_bytes, "base64")


def test_standard():
    test_strings = [
        "TEST TEST TEST\n",
        "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks.\n",
        "The computer can be used as a tool to liberate and protect people, rather than to control them.\n",
    ]
    return test_strings


def test_raw():
    # Lightning handshake messages captured from lnproxy
    test_handshake_0 = b"\x00\x03U\xc7\xaa\xa3\x85\xe8%\x95M\x96\xcbQ\x80C\x04\x0f\xf0\x14\xcf\x10\x11{t\x93=\x9d}\xa8a\xf5r\x02w\xca;\x11\xa1T\xaa\x81\xbf\xf2\xcbr\xd5;\xa9\xb2"
    test_handshake_1 = b"\x00\x02L\xdf\xd9\x81\x98\xcfr\xd8\xa7d\xd2\x167\x98\xff\x9b\t\x16\x1cR\x82^\x96\t8\xfb[\x9fv\x15d\n\xc0\xf7Wi\xf2\x1f\x9f\xd6ht\xba.\xf0>\\\x1c"
    test_handshake_2 = b"\x00\xae);;\xcd\x02\xea\x12A\xfc@\xb6L\xd6\xd2.\x8by\xfc\xddIR\xd9\x9e\x86\x96j\xbf\x8cA\xec\x8aD\xb0\xf1\xcb\xd6\xedQzq\xc3,\xb3W_\xf25\x0b\x066j\xd7\x06\xd3\xa0\xf0i=\xcd\xd8J\xb0\xffv"
    test_handshake_3 = b'\x00-\x00\x10\x00\x02"\x00\x00\x03\x02\xaa\xa2\x01 \x06"nF\x11\x1a\x0bY\xca\xaf\x12`C\xeb[\xbf(\xc3O:^3*\x1f\xc7\xb2\xb7<\xf1\x88\x91\x0f'
    handshakes = [
        test_handshake_0,
        test_handshake_1,
        test_handshake_2,
        test_handshake_3,
    ]
    handshakes_base64 = []
    hs_test = True
    for hs_message in handshakes:
        hs_base64 = raw_to_base64(hs_message, prefix=b"")
        print(hs_base64)
        # check for successful newline stripping
        if hs_base64.count(b"\n") != 1:
            print("newline stripping failed!")
            hs_test = False
            break
        hs_raw = base64_to_raw(hs_base64)
        if hs_raw != hs_message:
            print("encode/decode fail!")
            hs_test = False
            break
        else:
            handshakes_base64.append(hs_base64)
    if hs_test is True:
        return handshakes_base64


def parse_args():
    # fmt: off
    parser = argparse.ArgumentParser(description="Talk to fldigi.")
    parser.add_argument("--xml", type=int, help="XML-RPC port")
    parser.add_argument("--nohead", help="run fldigi without a GUI", action="store_true")
    parser.add_argument("--noproxy", help="run without TCP proxy functionality", action="store_true")
    parser.add_argument("--proxy_in", type=int, help="TCP port lnproxy listening on for inbound connections from node")
    parser.add_argument("--proxy_out", type=int, help="TCP port for lnproxy to connect to when making outbound connections to node")
    parser.add_argument("--carrier", type=int, help="set carrier frequency in Hz; disables AFC")
    parser.add_argument("--modem", type=str, help="select a specific modem")
    parser.add_argument('--rigmode', type=str, help="select a transceiver mode")
    # fmt: on
    args = parser.parse_args()
    print(
        "args:",
        args.xml,
        args.nohead,
        args.noproxy,
        args.proxy_in,
        args.proxy_out,
        args.carrier,
        args.modem,
    )
    return args


def fl_radio_settings(fl_main, args):
    print(fl_main.version())
    fl_main.port_info()
    fl_main.rig_info()
    fl_main.modem_info()
    if args.rigmode is not None:
        fl_main.rig_modify(mode=args.rigmode)
        print("transceiver mode now", args.rigmode)
    else:
        print("Defaulting to USB transceiver mode")
        fl_main.rig_modify(mode="USB")
    if args.modem is not None:
        fl_main.modem_modify(modem=args.modem)
        print("modem now", args.modem)
    else:
        print("Defaulting to PSK125R")
        fl_main.modem_modify(modem="PSK125R")
    if fl_main.fl_client.modem.name in fl_main.modem_timeout_multipliers:
        fl_main.send_timeout_multiplier = fl_main.modem_timeout_multipliers[
            fl_main.fl_client.modem.name
        ]
    else:
        print("No stored multiplier for how many seconds per byte your modem will do")
        print("Defaulting to multiplier for PSK125R")
        fl_main.send_timeout_multiplier = fl_main.modem_timeout_multipliers["PSK125R"]
    if args.carrier is not None:
        fl_main.modem_modify(carrier=args.carrier)
        print("carrier frequency now", args.carrier, "Hz, AFC off")
    else:
        print("Defaulting to 1500 Hz carrier with AFC off")
        fl_main.modem_modify(carrier=1500)
