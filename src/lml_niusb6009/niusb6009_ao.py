#!/bin/env python
import usb.core
import time

import struct
#from typing import Optional

#from dataclasses import dataclass

from usb.legacy import USBError

from lml_niusb6009.niusb6009_common import Subsystem, Opcode, CONST, AoChannel
from lml_niusb6009.niusb6009_common import build_subsystem_cmd
from lml_niusb6009.niusb6009_common import parse_response
from lml_niusb6009.niusb6009_common import usb_device_context
from lml_niusb6009.niusb6009_common import send_cmd, do_read
#from lml_niusb6009.niusb6009_common import cmdLineArgs

# Actual capture data:
#                        op   sb      |nch  1stch 2ndch ...
# h->d: 0001 0010 000c 010f 0202 00 00 0004 0000 # 1 diff ch

# 0001 0010 000c 010e 0221 0000 018e 0000
# 0001 0012 000e 010e 0221 0000 0000 03e8 0000
# 0001 0012 000e 010e02210000000003e80000

def build_ao_command(channel: AoChannel, Vout: int) -> bytes:
    payload = ( struct.pack(">H", channel) + struct.pack(">H", Vout) +
                bytes([0x00, 0x00]))
    return build_subsystem_cmd(Opcode.OPEN, Subsystem.AO, payload, zeroWordBeforeData=False)

# Response Model
def send_cmd_rcv_ACK(dev: usb.core.Device, command: bytes, command_name: str) -> None:
    print(command.hex())
    send_cmd(dev, command)
    response: bytes = do_read(device)
    print(response.hex())
    resp_ddm = parse_response(response)
    if resp_ddm != {"kind":"ack"}:
        raise ValueError(f"Incorrect ACK for {command_name:s}")


## top level orchestrator

def write_ao(dev: usb.core.Device, channel: AoChannel, Vout: int) -> None:

    command: bytes = build_ao_command(channel, Vout)
    send_cmd_rcv_ACK(dev, command, "build_ai_channel_list")

def V_to_Vout(Vout: float) -> int:
    return int(Vout*1000.0 / 4.89) * 4



if __name__ == "__main__":
    """
    10 bit 
    0000 -> 3 mV
    4092 -> 5010 mV
    4.89 mV / step
    """
    with usb_device_context(CONST.VID, CONST.PID) as device:
        try:
            write_ao(device, AoChannel.AO0, V_to_Vout(2.5))
            write_ao(device, AoChannel.AO1, 4092)
        #            for i in range(51):
#                print(i*100)
#                write_ao(device, AoChannel.AO0, i*100)
#                input("Press Enter to continue")
        except USBError as e:
            pass
        except Exception as e:
            print(f"Main error: {e}")
