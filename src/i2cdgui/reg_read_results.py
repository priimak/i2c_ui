from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShowRegSignalData:
    register_address: str
    hexval: str
    binval: str
    highlight: bool
    address_bus_width_in_bytes: int
