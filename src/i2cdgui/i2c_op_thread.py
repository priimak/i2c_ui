import time
from queue import Queue

from bitstring import BitArray
from i2c_api import I2CMaster, RegisterAddress
from PySide6.QtCore import QThread, Signal

from i2cdgui.reg_read_results import ShowRegSignalData


class Command:
    pass


class WithAddrStr:
    def address_str(self) -> str:
        return f"0x{self.register_address:0{self.address_bus_width_in_bytes * 2}X}"


class ReadRegister(Command):
    __match_args__ = (
        "device_address",
        "register_address",
        "address_bus_width_in_bytes",
        "num_bytes",
        "highlight",
    )

    def __init__(
        self,
        *,
        device_address: int,
        register_address: int,
        address_bus_width_in_bytes: int,
        num_bytes: int,
        highlight: bool,
    ):
        self.device_address = device_address
        self.register_address = register_address
        self.address_bus_width_in_bytes = address_bus_width_in_bytes
        self.num_bytes = num_bytes
        self.highlight = highlight

    def address_str(self) -> str:
        return f"0x{self.register_address:0{self.address_bus_width_in_bytes * 2}X}"


class WriteRegister(Command):
    __match_args__ = (
        "device_address",
        "register_address",
        "address_bus_width_in_bytes",
        "register_value",
    )

    def __init__(
        self,
        device_address: int,
        register_address: int,
        address_bus_width_in_bytes: int,
        register_value: BitArray,
    ):
        self.device_address = device_address
        self.register_address = register_address
        self.address_bus_width_in_bytes = address_bus_width_in_bytes
        self.register_value = register_value

    def address_str(self) -> str:
        return f"0x{self.register_address:0{self.address_bus_width_in_bytes * 2}X}"


class TimedCommand(Command):
    def __init__(self, delay_millis: int):
        self.delay_millis = delay_millis
        self.submitted_at_millis = int(time.time() * 1000)

    def has_expired(self) -> bool:
        return (time.time() * 1000 - self.submitted_at_millis) >= self.delay_millis


class RequestReadAllRegisters(TimedCommand):
    pass


class HighlightOff(TimedCommand):
    pass


class Quit:
    pass


class I2COpThread(QThread):
    show_error = Signal(str)
    show_register_value = Signal(ShowRegSignalData)
    highlight_register_at_addr = Signal(str)
    request_re_read_all_registers = Signal()
    request_highlight_off = Signal()

    def __init__(self, /):
        super().__init__()
        self.commands = Queue()
        self._i2c_driver: I2CMaster | None = None

    @property
    def i2c(self) -> I2CMaster | None:
        return self._i2c_driver

    def write_register_at_addr(
        self,
        write_cmd: WriteRegister,
        read_back: bool,
    ) -> None:
        if write_cmd.device_address == -1:
            self.show_error.emit("Please select device address to read registers from")
        else:
            try:
                self.highlight_register_at_addr.emit(write_cmd.address_str())
                regval = self.i2c.write_register(
                    write_cmd.device_address,
                    RegisterAddress(
                        write_cmd.register_address, write_cmd.address_bus_width_in_bytes
                    ),
                    write_cmd.register_value,
                    num_bytes=None,
                    read_back=read_back,
                    use_restart=True,
                )
                if regval is None:
                    self.show_error.emit(
                        f"Failed to read back register at address {write_cmd.address_str()}"
                    )
                else:
                    self.show_register_value.emit(
                        ShowRegSignalData(
                            write_cmd.address_str(),
                            f"0x{regval.uint:02X}",
                            regval.bin,
                            highlight=True,
                            address_bus_width_in_bytes=write_cmd.address_bus_width_in_bytes,
                        )
                    )
            except Exception as ex:
                self.show_error.emit(f"{ex}")

    def read_register_at_addr(self, read_cmd: ReadRegister) -> None:
        if read_cmd.device_address == -1:
            self.show_error.emit("Please select device address to read registers from")
        else:
            try:
                if read_cmd.highlight:
                    self.highlight_register_at_addr.emit(read_cmd.address_str())
                regval = self.i2c.read_register(
                    read_cmd.device_address,
                    RegisterAddress(
                        read_cmd.register_address, read_cmd.address_bus_width_in_bytes
                    ),
                    read_cmd.num_bytes,
                    use_restart=True,
                )
                if regval is None:
                    self.show_error.emit(
                        f"Failed to read register at address {read_cmd.address_str()}"
                    )
                else:
                    self.show_register_value.emit(
                        ShowRegSignalData(
                            read_cmd.address_str(),
                            f"0x{regval.uint:02X}",
                            regval.bin,
                            highlight=read_cmd.highlight,
                            address_bus_width_in_bytes=read_cmd.address_bus_width_in_bytes,
                        )
                    )
            except Exception as ex:
                self.show_error.emit(f"{ex}")

    def run(self) -> None:
        while True:
            cmd = self.commands.get()
            match cmd:
                case ReadRegister():
                    self.read_register_at_addr(cmd)

                case RequestReadAllRegisters():
                    if cmd.has_expired():
                        self.request_re_read_all_registers.emit()
                    else:
                        self.commands.put(cmd)

                case WriteRegister():
                    self.write_register_at_addr(write_cmd=cmd, read_back=True)

                case HighlightOff():
                    if cmd.has_expired():
                        self.request_highlight_off.emit()
                    else:
                        self.commands.put(cmd)

                case Quit():
                    return
