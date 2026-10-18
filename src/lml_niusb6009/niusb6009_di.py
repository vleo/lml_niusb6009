#!/bin/env python
import usb.core

import struct
from typing import Optional

from dataclasses import dataclass

from lml_niusb6009.niusb6009_common import Subsystem, Opcode, Port, DiTag, CONST
from lml_niusb6009.niusb6009_common import build_subsystem_cmd
from lml_niusb6009.niusb6009_common import ACK_BYTES
from lml_niusb6009.niusb6009_common import usb_device_context
from lml_niusb6009.niusb6009_common import send_cmd, do_read
from lml_niusb6009.niusb6009_common import cmdLineArgs


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
    # noinspection PyTypeChecker
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

def read_di(dev: usb.core.Device, *ports: Port) -> DigitalInResult:
    command: bytes = digital_in_command(*ports)
    send_cmd(dev, command)
    response: bytes = do_read(device)
    resp_di: DigitalInResult = digital_in_parse(response, (Port.P0, Port.P1))
    return resp_di



if __name__ == "__main__":
    with usb_device_context(CONST.VID, CONST.PID) as device:
        try:
            ###################################################
            commandm = digital_in_command(Port.P0, Port.P1)
            print(commandm.hex())
            send_cmd(device,commandm)

            responsem = do_read(device)
            print(responsem.hex())
            rdi = digital_in_parse(responsem, (Port.P0, Port.P1))

            if rdi.port0 is not None:
                print(rdi.port0.state)            # 0xf5
                print(rdi.port0.lines)            # (True, False, True, False, True, True, True, True)
                print(rdi.port0.line(0))          # True
            if rdi.port1 is not None:
                print(rdi.port1.state)            # 0xfd
                print(rdi.port1.lines)            # (True, False, True, True)
                print(rdi.port1.upper_nibble)     # 0xf (don't care on USB-6009)
            ###################################################
        except RuntimeError as e:
            print("Main error: {e}")
