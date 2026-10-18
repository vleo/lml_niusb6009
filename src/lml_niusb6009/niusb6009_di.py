#!/bin/env python
import usb.core
import usb.util
import time

import struct
from enum import IntEnum
from typing import Optional

from dataclasses import dataclass
from lml_common.immutable import FrozenClassMeta, freeze_class

@freeze_class
@dataclass(frozen=True)
class CONST(metaclass=FrozenClassMeta):
    VID: int = 0x3923
    PID: int =  0x717b
    EP_CMD_OUT: int = 0x01
    EP_ACK_IN:  int = 0x81
    EP_DGTL_IN: int = 0x81
    EP_ANLG_IN: int = 0x82

# # Endpoints on NI USB-6009:
# EP_CMD_OUT = 0x01   # host -> device: commands send
# EP_ACK_IN  = 0x81   # device -> host: commands ACK
# EP_DGTL_IN = 0x81   # device -> host: digital data read
# EP_ANLG_IN = 0x82   # device -> host: analog data read

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

## Envelope Builders

# `IntEnum` values are `int` subclasses, so `bytes([Subsystem.DIO])` and `struct.pack("<B", Subsystem.DIO)` both work directly.
# Make the enum usage explicit with `int(...)` where it clarifies intent.

def build_command(payload: bytes) -> bytes:
    total_len = 6 + len(payload)
    inner_len = 2 + len(payload)
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

## Digital Input — Command Builder

# (n_ports, sorted_port_ids) -> (tag, port_list_bytes)
_DI_FORMS = {
    (1, (Port.P0,)):         (DiTag.ONE_PORT,  bytes([Port.P0, 0x00])),
    (1, (Port.P1,)):         (DiTag.ONE_PORT,  bytes([Port.P1, 0x00])),
    (2, (Port.P0, Port.P1)): (DiTag.TWO_PORTS, bytes([Port.P0, Port.P1])),
}


def build_digital_in(ports: tuple[Port, ...]) -> bytes:
    """
    Build a digital input command.

    ports: tuple of Port values, e.g. (Port.P0,), (Port.P1,), or (Port.P0, Port.P1).
    Returns the full EP01 OUT packet.
    """
    key = (len(ports), tuple(sorted(ports)))
    if key not in _DI_FORMS:
        raise ValueError(f"unsupported digital input ports: {ports}")
    tag, port_bytes = _DI_FORMS[key]
    data = bytes([int(tag)]) + port_bytes
    return build_subsystem_cmd(Opcode.OPEN, Subsystem.DIO, data)

## Response Model

@dataclass(frozen=True)
class PortState:
    port: Port
    state: int
    lines: tuple[bool, ...]

    def line(self, n: int) -> bool:
        return self.lines[n]

    @property
    def upper_nibble(self) -> int:
        return (self.state >> 4) & 0xF


@dataclass(frozen=True)
class DigitalInResult:
    port0: Optional[PortState]
    port1: Optional[PortState]

    def state_of(self, port: Port) -> Optional[PortState]:
        return self.port0 if port == Port.P0 else self.port1

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

    outer_len = struct.unpack_from(">H", data, 2)[0]
    payload = data[4:4 + outer_len]

    if (len(payload) >= 12
            and payload[0:2] == b"\x00\x0c"
            and payload[6:8] == b"\x00\x02"
            and payload[8:10] in (b"\x00\x03", b"\x00\x04")):
        tag = struct.unpack_from(">H", payload, 8)[0]
        n_ports = tag - 2
        states = list(payload[10:10 + n_ports])
        return {"kind": "digital_in", "tag": tag, "states": states, "payload": payload}

    return {"kind": "unknown", "raw": data}


def decode_digital_in(result: dict, requested_ports: tuple[Port, ...]) -> DigitalInResult:
    """Map a digital_in response to per-port PortState objects."""
    if result["kind"] != "digital_in":
        raise ValueError(f"expected digital_in, got {result['kind']}")

    tag = DiTag(result["tag"])
    if tag == DiTag.ONE_PORT and len(requested_ports) != 1:
        raise ValueError("response has one port but multiple ports were requested")
    if tag == DiTag.TWO_PORTS and len(requested_ports) != 2:
        raise ValueError("response has two ports but only one was requested")

    port_map = dict(zip(requested_ports, result["states"]))

    def make(port_id: Port, state: Optional[int]) -> Optional[PortState]:
        if state is None:
            return None
        n_lines = 8 if port_id == Port.P0 else 4
        return PortState(
            port=port_id,
            state=state,
            lines=tuple(bool((state >> b) & 1) for b in range(n_lines)),
        )

    return DigitalInResult(
        port0=make(Port.P0, port_map.get(Port.P0)),
        port1=make(Port.P1, port_map.get(Port.P1)),
    )

## Convenience Wrappers

def digital_in_command(*ports: Port) -> bytes:
    return build_digital_in(tuple(ports))


def digital_in_parse(data: bytes, requested_ports: tuple[Port, ...]) -> DigitalInResult:
    return decode_digital_in(parse_response(data), requested_ports)

## Reusability — Same Primitives for Other Subsystems

def build_digital_out_config(dir_mask: int, drive_mask: int) -> bytes:
    data = (struct.pack("<H", 0x0004)
            + struct.pack("<H", dir_mask & 0xFFFF)
            + struct.pack("<H", 0x0004)
            + struct.pack("<H", drive_mask & 0xFFFF))
    return build_subsystem_cmd(Opcode.CONFIG, Subsystem.DIO, data)


def build_digital_out_write(port: Port, state: int) -> bytes:
    data = bytes([0x00, 0x03, int(port), 0x00, 0x03, state & 0xFF, 0x00, 0x00])
    return build_subsystem_cmd(Opcode.LIST_WRITE, Subsystem.DIO, data)


def build_analog_out(channel: AoChannel, code: int) -> bytes:
    data = struct.pack("<HH", int(channel), code & 0xFFFF) + b"\x00\x00"
    return build_subsystem_cmd(Opcode.OPEN, Subsystem.AO, data)


def build_ai_sample_request() -> bytes:
    return build_command(bytes.fromhex("01140203000000000001"))


def build_ai_commit() -> bytes:
    return build_lifecycle_cmd(Opcode.COMMIT, 0x00)

## Main

# def open_device(idVendor, idProduct) -> usb.core.Device:
#     dev :Optional[usb.core.Device] = usb.core.find(idVendor, idProduct)
#     if dev is None:
#         raise RuntimeError("USB-6009 clone not found")
#
#     # Detach kernel driver if it grabbed the interface
#     if dev.is_kernel_driver_active(0):
#         dev.detach_kernel_driver(0)
#
#     dev.set_configuration()
#     usb.util.claim_interface(dev, 0)
#     return dev
#
# #
def send_cmd(dev: usb.core.Device, cmd : bytes):
    """ NI-DAQmx start cmd sequence for a DI channels"""

    dev.write(CONST.EP_CMD_OUT, cmd, timeout=1000)

def do_read(dev):
    """ NI-DAQmx read sequence for a DI channels"""
    resp = bytes(dev.read(CONST.EP_DGTL_IN, 64, timeout=2000))
    return resp


import usb.core
import usb.util
import sys

# Replace with your device's Vendor and Product IDs (in hexadecimal)
VENDOR_ID = CONST.VID
PRODUCT_ID = CONST.PID

def open_usb_device():
    # 1. Find the device
    dev = usb.core.find(idVendor=CONST.VID, idProduct=CONST.PID)

    if dev is None:
        raise ValueError('Device not found. Check connections and IDs.')

    #print(f"Found device: {dev}")

    # 2. Detach kernel driver (Crucial for Linux)
    # This prevents the OS from holding the device "busy"
    try:
        if dev.is_kernel_driver_active(0):
            print("Detaching kernel driver...")
            dev.detach_kernel_driver(0)
    except NotImplementedError:
        # Windows and macOS generally don't use/need this
        pass
    except usb.core.USBError as e:
        print(f"Could not detach kernel driver: {e}")

     # 3. Set the active configuration
     # If no configuration is set, or it's already set, handle the exceptions
    try:
        dev.set_configuration()
    except usb.core.USBError as e:
        # Sometimes the device is already in the correct configuration
        if "Configuration not set" not in str(e) and "Resource busy" not in str(e):
            raise

    # 4. Claim the interface (Interface 0 is standard, change if needed)
    try:
        usb.util.claim_interface(dev, 0)
        # TODO: print if verbose
        #print("Successfully claimed interface 0.")
    except usb.core.USBError as e:
        print(f"Failed to claim interface: {e}")
        sys.exit(1)

    return dev


def close_usb_device(dev):
    """Properly release the device when done."""
    try:
        usb.util.release_interface(dev, 0)
    except Exception:
        pass

    try:
        # Re-attach the kernel driver so the OS can use it again
        dev.attach_kernel_driver(0)
    except Exception:
        pass

    usb.util.dispose_resources(dev)
    print("Device closed and released.")

if __name__ == "__main__":
    device = open_usb_device()
    try:
        ###################################################
        command = digital_in_command(Port.P0, Port.P1)
        print(command.hex())
        send_cmd(device,command)

        response = do_read(device)
        print(response.hex())
        r = digital_in_parse(response, (Port.P0, Port.P1))

        print(r.port0.state)            # 0xf5
        print(r.port0.lines)            # (True, False, True, False, True, True, True, True)
        print(r.port0.line(0))          # True
        print(r.port1.state)            # 0xfd
        print(r.port1.lines)            # (True, False, True, True)
        print(r.port1.upper_nibble)     # 0xf (don't-care on USB-6009)
        ###################################################
    finally:
        usb.util.release_interface(device, 0)
        usb.util.dispose_resources(device)
