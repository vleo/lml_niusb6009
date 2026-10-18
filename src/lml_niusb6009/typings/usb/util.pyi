from _typeshed import Incomplete

DESC_TYPE_DEVICE: int
DESC_TYPE_CONFIG: int
DESC_TYPE_STRING: int
DESC_TYPE_INTERFACE: int
DESC_TYPE_ENDPOINT: int
ENDPOINT_IN: int
ENDPOINT_OUT: int
ENDPOINT_TYPE_CTRL: int
ENDPOINT_TYPE_ISO: int
ENDPOINT_TYPE_BULK: int
ENDPOINT_TYPE_INTR: int
CTRL_TYPE_STANDARD: Incomplete
CTRL_TYPE_CLASS: Incomplete
CTRL_TYPE_VENDOR: Incomplete
CTRL_TYPE_RESERVED: Incomplete
CTRL_RECIPIENT_DEVICE: int
CTRL_RECIPIENT_INTERFACE: int
CTRL_RECIPIENT_ENDPOINT: int
CTRL_RECIPIENT_OTHER: int
CTRL_OUT: int
CTRL_IN: int
SPEED_LOW: int
SPEED_FULL: int
SPEED_HIGH: int
SPEED_SUPER: int
SPEED_UNKNOWN: int

def endpoint_address(address): ...
def endpoint_direction(address): ...
def endpoint_type(bmAttributes): ...
def ctrl_direction(bmRequestType): ...
def build_request_type(direction, type, recipient): ...
def create_buffer(length): ...
def find_descriptor(desc, find_all: bool = False, custom_match=None, **args): ...
def claim_interface(device, interface) -> None: ...
def release_interface(device, interface) -> None: ...
def dispose_resources(device) -> None: ...
def get_langids(dev): ...
def get_string(dev, index, langid=None): ...
