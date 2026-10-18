import usb._objfinalizer as _objfinalizer
import usb.core as core
from _typeshed import Incomplete

USBError = core.USBError
CLASS_AUDIO: int
CLASS_COMM: int
CLASS_DATA: int
CLASS_HID: int
CLASS_HUB: int
CLASS_MASS_STORAGE: int
CLASS_PER_INTERFACE: int
CLASS_PRINTER: int
CLASS_WIRELESS_CONTROLLER: int
CLASS_VENDOR_SPEC: int
DT_CONFIG: int
DT_CONFIG_SIZE: int
DT_DEVICE: int
DT_DEVICE_SIZE: int
DT_ENDPOINT: int
DT_ENDPOINT_AUDIO_SIZE: int
DT_ENDPOINT_SIZE: int
DT_HID: int
DT_HUB: int
DT_HUB_NONVAR_SIZE: int
DT_INTERFACE: int
DT_INTERFACE_SIZE: int
DT_PHYSICAL: int
DT_REPORT: int
DT_STRING: int
ENDPOINT_ADDRESS_MASK: int
ENDPOINT_DIR_MASK: int
ENDPOINT_IN: int
ENDPOINT_OUT: int
ENDPOINT_TYPE_BULK: int
ENDPOINT_TYPE_CONTROL: int
ENDPOINT_TYPE_INTERRUPT: int
ENDPOINT_TYPE_ISOCHRONOUS: int
ENDPOINT_TYPE_MASK: int
ERROR_BEGIN: int
MAXALTSETTING: int
MAXCONFIG: int
MAXENDPOINTS: int
MAXINTERFACES: int
PROTOCOL_BLUETOOTH_PRIMARY_CONTROLLER: int
RECIP_DEVICE: int
RECIP_ENDPOINT: int
RECIP_INTERFACE: int
RECIP_OTHER: int
REQ_CLEAR_FEATURE: int
REQ_GET_CONFIGURATION: int
REQ_GET_DESCRIPTOR: int
REQ_GET_INTERFACE: int
REQ_GET_STATUS: int
REQ_SET_ADDRESS: int
REQ_SET_CONFIGURATION: int
REQ_SET_DESCRIPTOR: int
REQ_SET_FEATURE: int
REQ_SET_INTERFACE: int
REQ_SYNCH_FRAME: int
SUBCLASS_RF_CONTROLLER: int
TYPE_CLASS: int
TYPE_RESERVED: int
TYPE_STANDARD: int
TYPE_VENDOR: int

class Endpoint:
    address: Incomplete
    interval: Incomplete
    maxPacketSize: Incomplete
    type: Incomplete
    def __init__(self, ep) -> None: ...

class Interface:
    alternateSetting: Incomplete
    interfaceNumber: Incomplete
    iInterface: Incomplete
    interfaceClass: Incomplete
    interfaceSubClass: Incomplete
    interfaceProtocol: Incomplete
    endpoints: Incomplete
    def __init__(self, intf) -> None: ...

class Configuration:
    iConfiguration: Incomplete
    maxPower: Incomplete
    remoteWakeup: Incomplete
    selfPowered: Incomplete
    totalLength: Incomplete
    value: Incomplete
    interfaces: Incomplete
    def __init__(self, cfg) -> None: ...

class DeviceHandle(_objfinalizer.AutoFinalizedObject):
    dev: Incomplete
    def __init__(self, dev) -> None: ...
    def bulkWrite(self, endpoint, buffer, timeout: int = 100): ...
    def bulkRead(self, endpoint, size, timeout: int = 100): ...
    def interruptWrite(self, endpoint, buffer, timeout: int = 100): ...
    def interruptRead(self, endpoint, size, timeout: int = 100): ...
    def controlMsg(self, requestType, request, buffer, value: int = 0, index: int = 0, timeout: int = 100): ...
    def clearHalt(self, endpoint) -> None: ...
    def claimInterface(self, interface) -> None: ...
    def releaseInterface(self) -> None: ...
    def reset(self) -> None: ...
    def resetEndpoint(self, endpoint) -> None: ...
    def setConfiguration(self, configuration) -> None: ...
    def setAltInterface(self, alternate) -> None: ...
    def getString(self, index, length, langid=None): ...
    def getDescriptor(self, desc_type, desc_index, length, endpoint: int = -1): ...
    def detachKernelDriver(self, interface) -> None: ...

class Device:
    deviceClass: Incomplete
    deviceSubClass: Incomplete
    deviceProtocol: Incomplete
    deviceVersion: Incomplete
    devnum: Incomplete
    filename: str
    iManufacturer: Incomplete
    iProduct: Incomplete
    iSerialNumber: Incomplete
    idProduct: Incomplete
    idVendor: Incomplete
    maxPacketSize: Incomplete
    usbVersion: Incomplete
    configurations: Incomplete
    dev: Incomplete
    def __init__(self, dev) -> None: ...
    def open(self): ...

class Bus:
    dirname: str
    devices: Incomplete
    location: Incomplete
    def __init__(self, devices) -> None: ...

def busses(): ...
