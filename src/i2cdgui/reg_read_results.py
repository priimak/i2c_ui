from dataclasses import dataclass


@dataclass(slots=True)
class ShowRegSignalData:
    register_address: str
    hexval: str
    binval: str
    highlight: bool
