#!/bin/env python
import usb.core
import time

import struct
from typing import Optional

from dataclasses import dataclass

from usb.legacy import USBError

from lml_niusb6009.niusb6009_common import Subsystem, Opcode, Port, CONST, AiChannel, AiMode, build_command, \
    send_adc_req, do_read_adc
from lml_niusb6009.niusb6009_common import build_subsystem_cmd
from lml_niusb6009.niusb6009_common import parse_response
from lml_niusb6009.niusb6009_common import usb_device_context
from lml_niusb6009.niusb6009_common import send_cmd, do_read
from lml_niusb6009.niusb6009_common import cmdLineArgs

#                                     | <-- payload    -->|
#                        op   sb      |      dir       drv
# h->d: 0001 0014 0010 0112 0210 00 00 0004 000f 0004 0000   # direction and drive type

#                                     | <-- payload     -->|
#                        op   sb      |    port    data
# h->d: 0001 0014 0010 010f 0210 00 00 0003 00 0003 a5 0000
# h->d: 0001 0014 0010 010f 0210 00 00 0003 01 0003 0f 0000

# 00010010000c010f0202000000040000 good
# 00010010000c010f0202000000040000
# 000100140010010f020200000006000000010000 good
#
# Actual capture data:
#                        op   sb      |nch  1stch 2ndch ...
# h->d: 0001 0010 000c 010f 0202 00 00 0004 0000 # 1 diff ch
# h->d: 0001 0010 000c 010f 0202 00 00 0006 0000 0001 0000 # 2 diff ch
# h->d: 0001 0010 000c 010f 0202 00 00 0008 0000 0001 0002 # 3 diff ch
# h->d: 0001 0010 000c 010f 0202 00 00 000a 0000 0001 0002 0003 0000 # 4 diff ch
# The intermittent trailing 0000 is NI driver padding with no apparent
# device-side purpose. Not exhaustively tested, but our driver omits it.
def build_ai_channel_list(channels: tuple[AiChannel, ...]) -> bytes:
    number_of_channels_code: int = 2 + 2 * len(channels)
    payload: bytes = bytes([0x00, number_of_channels_code])
    for ch in channels:
        payload += struct.pack(">H", ch)
    return build_subsystem_cmd(Opcode.LIST_WRITE, Subsystem.AI, payload)

# 1 to 4 DIFF
#                        op   sb      |   nch 1stchmode  2ndchmode ...
# h->d: 0001 0010 000c 010e 0202 00 00 00 03 00 00 <- uneeded 00 padding
# h->d: 0001 0010 000c 010e 0202 00 00 00 04 00 00
# 000100140010010e020200000005000000000000
# 000100140010010e020200000006000000000000
# 1 to 8 RSE
# 00010010000c010e0202000000030200
# 00010010000c010e0202000000040202
# 000100140010010e020200000005020202000000
# 000100140010010e020200000006020202020000
# 000100140010010e020200000007020202020200
# 000100140010010e020200000008020202020202
# 000100180014010e02020000000902020202020202000000
# 000100180014010e02020000000a02020202020202020000

def build_ai_mode_vector(modes: tuple[AiMode, ...]) -> bytes:
    """01 0e 02 02 00 00 <count> <mode_0> <mode_1> ..."""
    number_of_channels_code: int = 2 + len(modes)
    data = bytes([0x00, number_of_channels_code] + [int(m) for m in modes])
    return build_subsystem_cmd(Opcode.OPEN, Subsystem.AI, data)

# h->d: 0001 001c 0018 0110 0202 00 00 00 00 2710 ffff d8f0 fdfd 0004 0000 0000 # good

# 0001001c001801100202000000002710ffffd8f0fdfd000400000000 # good
# 0001001a001601100202000000002710ffffd8f0fdfd00040000 # mine good works too for -10000, 10000
def build_ai_range(min_mV: int, max_mV: int, channels: tuple[AiChannel, ...]) -> bytes:
    number_of_channels_code: int = 2 + 2 * len(channels)
    noc : bytes = struct.pack(">H", number_of_channels_code)

    payload = bytes([0x00, 0x00])
    payload += max_mV.to_bytes(2, "big", signed=True)
    payload += bytes([0xff, 0xff])
    payload += min_mV.to_bytes(2, "big", signed=True)
    payload += bytes([0xFD, 0xFD])
    payload += noc

    for ch in channels:
        payload += struct.pack(">H", ch)
    return build_subsystem_cmd(Opcode.RANGE, Subsystem.AI, payload)

# analog in magic preamble:
AI_MAGIC_PREAMBLE = [
    # 00010010000c010e0200000000000000 # good
    # 010e0200000000000000
    [0x01, 0x0e, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,],
    [0x01, 0x0f, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01,],
    [0x01, 0x13, 0x02, 0x00, 0x00, 0x00,],
    [0x01, 0x15, 0x02, 0x00, 0x00, 0x00,],
    [0x01, 0x18, 0x02, 0x00, 0x00, 0x00,],
    [0x01, 0x0f, 0x02, 0x03, 0x00, 0x00,],
    [0x01, 0x09, 0x02, 0x03, 0x00, 0x00,],
    [0x01, 0x09, 0x02, 0x00, 0x00, 0x00,],
]
# request ADC data
AI_REQEST_SAMPLE = [0x00, 0x14, 0x02, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01]

AI_MAGIC_TEARDOWN = [
    [0x01, 0x0b, 0x02, 0x00, 0x00, 0x00, ],
    [0x01, 0x0c, 0x02, 0x00, 0x00, 0x00, ],
    [0x01, 0x0c, 0x02, 0x03, 0x00, 0x00, ],
    [0x01, 0x0d, 0x02, 0x00, 0x00, 0x00, ],
]

## Response Model
def send_cmd_rcv_ACK(dev: usb.core.Device, command: bytes, command_name: str) -> None:
    print(command.hex())
    send_cmd(dev, command)
    response: bytes = do_read(device)
    print(response.hex())
    resp_ddm = parse_response(response)
    if resp_ddm != {"kind":"ack"}:
        raise ValueError(f"Incorrect ACK for {command_name:s}")


## top level orchestrator

def read_ai(dev: usb.core.Device, min_mV, max_mV, diff_mode: AiMode, *channels: AiChannel) -> tuple[int]:

    command: bytes = build_ai_channel_list(channels)
    send_cmd_rcv_ACK(dev, command, "build_ai_channel_list")

    command = build_ai_mode_vector(tuple([diff_mode] * len(tuple(channels))))
    send_cmd_rcv_ACK(dev, command, "build_ai_mode_vector")

    command = build_ai_range(min_mV, max_mV, channels)
    send_cmd_rcv_ACK(dev, command, "build_ai_range")

    for i in range(0,len(AI_MAGIC_PREAMBLE)):
        command = bytes(AI_MAGIC_PREAMBLE[i])
        send_cmd_rcv_ACK(dev, build_command(command) , f"AI_MAGIC_PREAMBLE_{i:d}")

    #time.sleep(2.0)

    command = bytes(AI_REQEST_SAMPLE)
    cmd = build_command(command)
    print("REQ SAMPLE:", cmd.hex())
    send_cmd(dev, cmd)

    response: bytes = do_read_adc(device)
    print("SAMPLE:", response.hex())

    nch = len(channels)
    values: tuple[int] = struct.unpack(f">{nch:d}H", response)
    print("VALUES:", values)

    for i in range(0,len(AI_MAGIC_TEARDOWN)):
        command = bytes(AI_MAGIC_TEARDOWN[i])
        send_cmd_rcv_ACK(dev, build_command(command) , f"AI_MAGIC_TEARDOWN_{i:d}")

    return values



if __name__ == "__main__":
    with usb_device_context(CONST.VID, CONST.PID) as device:
        try:
            #read_ai(device, -10000, 10000, AiMode.DIFF, AiChannel.AI0)
            #read_ai(device, -5000, 5000, AiMode.DIFF, AiChannel.AI0)
            read_ai(device, -2000, 2000, AiMode.DIFF, AiChannel.AI0)
            #read_ai(device, -10000, 10000, AiMode.DIFF, AiChannel.AI0, AiChannel.AI1)
            # read_ai(device, 0, 4096, AiMode.DIFF, AiChannel.AI0, AiChannel.AI1, AiChannel.AI2)
            # read_ai(device, 0, 4096, AiMode.DIFF, AiChannel.AI0, AiChannel.AI1, AiChannel.AI2, AiChannel.AI3)
        except USBError as e:
            pass
        except Exception as e:
            print(f"Main error: {e}")
