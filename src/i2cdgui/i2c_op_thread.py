import time
from queue import Queue

from bitstring import BitArray
from i2c_api import I2CMaster
from PySide6.QtCore import QThread, Signal

from i2cdgui.reg_read_results import ShowRegSignalData


class Command:
    pass


class ReadRegister(Command):
    __match_args__ = ("device_address", "register_address", "num_bytes", "highlight")

    def __init__(
        self,
        device_address: int,
        register_address: int,
        num_bytes: int,
        highlight: bool,
    ):
        self.device_address = device_address
        self.register_address = register_address
        self.num_bytes = num_bytes
        self.highlight = highlight


class WriteRegister(Command):
    __match_args__ = ("device_address", "register_address", "register_value")

    def __init__(
        self, device_address: int, register_address: int, register_value: BitArray
    ):
        self.device_address = device_address
        self.register_address = register_address
        self.register_value = register_value


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
        device_address: int,
        register_address: int,
        register_value: BitArray,
        read_back: bool,
    ) -> None:
        if device_address == -1:
            self.show_error.emit("Please select device address to read registers from")
        else:
            try:
                self.highlight_register_at_addr.emit(f"0x{register_address:02X}")
                regval = self.i2c.write_register(
                    device_address,
                    register_address,
                    register_value,
                    num_bytes=None,
                    read_back=read_back,
                    use_restart=True,
                )
                if regval is None:
                    self.show_error.emit(
                        f"Failed to read back register at address 0x{register_address:02X}"
                    )
                else:
                    self.show_register_value.emit(
                        ShowRegSignalData(
                            f"0x{register_address:02X}",
                            f"0x{regval.uint:02X}",
                            regval.bin,
                            highlight=True,
                        )
                    )
            except Exception as ex:
                self.show_error.emit(f"{ex}")

    def read_register_at_addr(
        self,
        device_address: int,
        register_address: int,
        num_bytes: int,
        highlight: bool,
    ) -> None:
        if device_address == -1:
            self.show_error.emit("Please select device address to read registers from")
        else:
            try:
                if highlight:
                    self.highlight_register_at_addr.emit(f"0x{register_address:02X}")
                regval = self.i2c.read_register(
                    device_address, register_address, num_bytes, use_restart=True
                )
                if regval is None:
                    self.show_error.emit(
                        f"Failed to read register at address 0x{register_address:02X}"
                    )
                else:
                    self.show_register_value.emit(
                        ShowRegSignalData(
                            f"0x{register_address:02X}",
                            f"0x{regval.uint:02X}",
                            regval.bin,
                            highlight,
                        )
                    )
            except Exception as ex:
                self.show_error.emit(f"{ex}")

    def run(self) -> None:
        while True:
            cmd = self.commands.get()
            match cmd:
                case ReadRegister(
                    device_address, register_address, num_bytes, highlight
                ):
                    self.read_register_at_addr(
                        device_address, register_address, num_bytes, highlight
                    )

                case RequestReadAllRegisters():
                    if cmd.has_expired():
                        self.request_re_read_all_registers.emit()
                    else:
                        self.commands.put(cmd)

                case WriteRegister(device_address, register_address, register_value):
                    self.write_register_at_addr(
                        device_address, register_address, register_value, read_back=True
                    )

                case HighlightOff():
                    if cmd.has_expired():
                        self.request_highlight_off.emit()
                    else:
                        self.commands.put(cmd)

                case Quit():
                    return
