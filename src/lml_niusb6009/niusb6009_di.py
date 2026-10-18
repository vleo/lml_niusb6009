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
from lml_niusb6009.niusb6009_common import parse_response
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

def read_di(dev: usb.core.Device, *ports: Port) -> DigitalInResult:
    command: bytes = build_digital_in(tuple(ports))
    print(command.hex())
    send_cmd(dev, command)
    response: bytes = do_read(device)
    print(response.hex())
    resp_di: DigitalInResult = decode_digital_in(parse_response(response), (Port.P0, Port.P1))
    return resp_di



if __name__ == "__main__":
    with usb_device_context(CONST.VID, CONST.PID) as device:
        try:
            rdi : DigitalInResult = read_di(device, Port.P0, Port.P1)

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
