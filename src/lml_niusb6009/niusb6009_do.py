#!/bin/env python
import usb.core

import struct
from typing import Optional

from usb.legacy import USBError

from lml_niusb6009.niusb6009_common import Subsystem, Opcode, Port, CONST
from lml_niusb6009.niusb6009_common import build_subsystem_cmd
from lml_niusb6009.niusb6009_common import parse_response
from lml_niusb6009.niusb6009_common import usb_device_context
from lml_niusb6009.niusb6009_common import send_cmd, do_read
from lml_niusb6009.niusb6009_common import cmdLineArgs

#                                     | <-- payload    -->|
#                        op   sb      |      dir       drv
# h->d: 0001 0014 0010 0112 0210 00 00 0004 000f 0004 0000   # direction and drive type

def build_digital_out_config(dir_mask: int, drive_mask: int) -> bytes:
    # noinspection PyTypeChecker
    payload = (struct.pack(">H", 0x0004)
            + struct.pack(">H", dir_mask & 0xFFFF)
            + struct.pack(">H", 0x0004)
            + struct.pack(">H", drive_mask & 0xFFFF))
    return build_subsystem_cmd(Opcode.CONFIG, Subsystem.DIO, payload)

#                                     | <-- payload     -->|
#                        op   sb      |    port    data
# h->d: 0001 0014 0010 010f 0210 00 00 0003 00 0003 a5 0000
# h->d: 0001 0014 0010 010f 0210 00 00 0003 01 0003 0f 0000
def build_digital_out_write(port: Port, state: int) -> bytes:
    payload = bytes([0x00, 0x03, int(port), 0x00, 0x03, state & 0xFF, 0x00, 0x00])
    return build_subsystem_cmd(Opcode.LIST_WRITE, Subsystem.DIO, payload)



# Convenience Wrappers

def write_ddm(dev: usb.core.Device, dir_mask: int = 0x00, drive_mask : int = 0x00) -> None:
    """
        dir_mask:   1 -> output;       0 -> input;
        drive_mask: 1 -> active drive; 0 -> open collector;
        0xhl port0 0xFl port1
        hhhh llll port 0 nnnn llll port1
    """
    command: bytes = build_digital_out_config(dir_mask,drive_mask)
    print(command.hex())
    send_cmd(dev, command)
    response: bytes = do_read(device)
    print(response.hex())
    resp_ddm = parse_response(response)

    if resp_ddm != {"kind":"ack"}:
        raise ValueError("Incorrect ACK for do direction/drive_type")

def write_do(dev: usb.core.Device, port: Port = Port.P0 , data:int = 0xFF) -> None:
    command: bytes = build_digital_out_write(port, data)
    print(command.hex())
    send_cmd(dev, command)
    response: bytes = do_read(device)
    print(response.hex())
    resp_ddm = parse_response(response)

    if resp_ddm != {"kind":"ack"}:
        raise ValueError("Incorrect ACK for do data")


if __name__ == "__main__":
    with usb_device_context(CONST.VID, CONST.PID) as device:
        try:
            if cmdLineArgs.reset:
                write_ddm(device) # everytrhing input, drivers - open collector
            else:
                write_ddm(device, 0xFF0F, 0x0000)
                write_do(device, Port.P0, 0xAA)
                write_do(device, Port.P1, 0x05)
        except USBError as e:
            pass
        except Exception as e:
            print(f"Main error: {e}")
