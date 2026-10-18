#!/bin/env python
import usb.core
import usb.util
from contextlib import contextmanager

# import time

import struct
from enum import IntEnum

from dataclasses import dataclass
from lml_common.immutable import FrozenClassMeta, freeze_class

import argparse

ap: argparse.ArgumentParser = argparse.ArgumentParser()
ap.add_argument("--verbose", action="store_true")

cmdLineArgs: argparse.Namespace = ap.parse_args()


@freeze_class
@dataclass(frozen=True)
class CONST(metaclass=FrozenClassMeta):
    VID: int = 0x3923
    PID: int =  0x717b
    EP_CMD_OUT: int = 0x01
    EP_ACK_IN:  int = 0x81
    EP_DGTL_IN: int = 0x81
    EP_ANLG_IN: int = 0x82

## Constants as Enums
class Subsystem(IntEnum):
    GENERIC = 0x00
    AI      = 0x02
    DIO     = 0x10
    AO      = 0x21


class Opcode(IntEnum):
    OPEN       = 0x0E
    LIST_WRITE = 0x0F
    RANGE      = 0x10
    CONFIG     = 0x12
    COMMIT     = 0x13
    SAMPLE     = 0x14
    ARM        = 0x15
    START      = 0x18
    STATUS     = 0x09
    STOP       = 0x0B
    RESET      = 0x0C
    CLOSE      = 0x0D


class Port(IntEnum):
    P0 = 0x00
    P1 = 0x01


class DiTag(IntEnum):
    ONE_PORT  = 0x03
    TWO_PORTS = 0x04


class AoChannel(IntEnum):
    AO0 = 0x0000
    AO1 = 0x0001

# (n_ports, sorted_port_ids) -> (tag, port_list_bytes)
_DIO_FORMS = {
    (1, (Port.P0,)):         (DiTag.ONE_PORT,  bytes([Port.P0, 0x00])),
    (1, (Port.P1,)):         (DiTag.ONE_PORT,  bytes([Port.P1, 0x00])),
    (2, (Port.P0, Port.P1)): (DiTag.TWO_PORTS, bytes([Port.P0, Port.P1])),
}

## Envelope Builders

# `IntEnum` values are `int` subclasses, so `bytes([Subsystem.DIO])` and `struct.pack("<B", Subsystem.DIO)` both work directly.
# Make the enum usage explicit with `int(...)` where it clarifies intent.

def build_command(payload: bytes) -> bytes:
    total_len = 6 + len(payload)
    inner_len = 2 + len(payload)
    # noinspection PyTypeChecker
    cmd =  b"\x00\x01" + struct.pack(">H", total_len) + struct.pack(">H", inner_len) + payload
    return cmd


def build_subsystem_cmd(opcode: Opcode, subsystem: Subsystem, data: bytes) -> bytes:
    """Build 01 <op> 02 <subsys> 00 00 <data>."""
    # noinspection PyTypeChecker
    payload = bytes([0x01, int(opcode), 0x02, int(subsystem), 0x00, 0x00, 0x00]) + data # type: ignore
    return build_command(payload)


def build_lifecycle_cmd(opcode: Opcode, state: int = 0x00) -> bytes:
    """Build 01 <op> 02 <state> 00 00."""
    payload = bytes([0x01, int(opcode), 0x02, state, 0x00, 0x00])
    return build_command(payload)

## Response Parser
ACK_BYTES = bytes.fromhex("0001000c0008010000000002")

def parse_response(data: bytes) -> dict:
    """
    Classify an EP81 IN packet.

    Returns one of:
      {"kind": "ack"}
      {"kind": "digital_in", "tag": int, "states": list[int], "payload": bytes}
      {"kind": "unknown", "raw": bytes}
    """
    if data == ACK_BYTES:
        return {"kind": "ack"}

    if len(data) < 4 or data[0:2] != b"\x00\x01":
        return {"kind": "unknown", "raw": data}

    # noinspection PyTypeChecker
    outer_len = struct.unpack_from(">H", data, 2)[0]
    payload = data[4:4 + outer_len]

    if (len(payload) >= 12
            and payload[0:2] == b"\x00\x0c"
            and payload[6:8] == b"\x00\x02"
            and payload[8:10] in (b"\x00\x03", b"\x00\x04")):
        # noinspection PyTypeChecker
        tag = struct.unpack_from(">H", payload, 8)[0]
        n_ports = tag - 2
        states = list(payload[10:10 + n_ports])
        return {"kind": "digital_in", "tag": tag, "states": states, "payload": payload}

    return {"kind": "unknown", "raw": data}
## Convenience Wrappers
## Reusability — Same Primitives for Other Subsystems

def build_digital_out_config(dir_mask: int, drive_mask: int) -> bytes:
    # noinspection PyTypeChecker
    data = (struct.pack("<H", 0x0004)
            + struct.pack("<H", dir_mask & 0xFFFF)
            + struct.pack("<H", 0x0004)
            + struct.pack("<H", drive_mask & 0xFFFF))
    return build_subsystem_cmd(Opcode.CONFIG, Subsystem.DIO, data)


def build_digital_out_write(port: Port, state: int) -> bytes:
    data = bytes([0x00, 0x03, int(port), 0x00, 0x03, state & 0xFF, 0x00, 0x00])
    return build_subsystem_cmd(Opcode.LIST_WRITE, Subsystem.DIO, data)


def build_analog_out(channel: AoChannel, code: int) -> bytes:
    # noinspection PyTypeChecker
    data = struct.pack("<HH", int(channel), code & 0xFFFF) + b"\x00\x00"
    return build_subsystem_cmd(Opcode.OPEN, Subsystem.AO, data)


def build_ai_sample_request() -> bytes:
    return build_command(bytes.fromhex("01140203000000000001"))


def build_ai_commit() -> bytes:
    return build_lifecycle_cmd(Opcode.COMMIT, 0x00)

def send_cmd(dev: usb.core.Device, cmd : bytes):
    """ NI-DAQmx start cmd sequence for a DI channels"""

    dev.write(CONST.EP_CMD_OUT, cmd, timeout=1000)

def do_read(dev):
    """ NI-DAQmx read sequence for a DI channels"""
    resp = bytes(dev.read(CONST.EP_DGTL_IN, 64, timeout=2000))
    return resp

@contextmanager
def usb_device_context(idVendor: int, idProduct: int):
    dev = usb.core.find(idVendor=idVendor, idProduct=idProduct)
    if dev is None:
        raise ValueError('Device not found.')

    was_driver_detached = False

    try:
        if dev.is_kernel_driver_active(0):
            print("Detaching kernel driver...")
            dev.detach_kernel_driver(0)
            was_driver_detached = True
    except NotImplementedError:
        pass
    except usb.core.USBError as e:
        print(f"Could not detach kernel driver: {e}")

    # Здесь можно добавить claim_interface, если нужно
    # usb.util.claim_interface(dev, 0)

    try:
        yield dev
    finally:
        # Блок очистки гарантированно выполнится даже при исключениях в теле with
        try:
            usb.util.release_interface(dev, 0)
        except RuntimeError as e:
            print(f"ignored RuntimeError: {e}")

        if was_driver_detached:
            try:
                dev.attach_kernel_driver(0)
                print("Kernel driver re-attached.")
            except usb.core.USBError as e:
                print(f"ignored USBError: {e}")
        else:
                print("No kernel driver to re-attach (none was active at start).") if cmdLineArgs.verbose else None

        usb.util.dispose_resources(dev)
        print("Device closed and released.") if cmdLineArgs.verbose else None


if __name__ == "__main__":
    with usb_device_context(CONST.VID, CONST.PID) as device:
        # Работа с устройством здесь
        # Например, чтение/запись, настройка, стриминг и т.п.
        print("Using device:", device)

