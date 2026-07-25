from typing import Callable
from typing import Optional

from i2c_api import I2CMaster
from i2capi_i2cdriver import I2CMasterI2CDriver
from i2cdgui.dummy_i2cmaster import DummyI2CMaster
from i2cdriver import I2CDriver
from sprats.config import AppPersistence


class App:
    def __init__(self, persistence: AppPersistence):
        self._i2c_driver: Optional[I2CMaster] = None
        self.port: str | None = None
        self.persistence = persistence
        self.i2c_master_changed: list[Callable[[I2CMaster],]] = []

        self.device_address: int = -1
        self.read_register_num_bytes: int = 1
        self.read_register_address_str = ""

        self.write_register_num_bytes: int = 1
        self.show_error: Callable[[str], None] = lambda _: None

        self.show_read_register_results: Callable[[str, str, str], None] = lambda a, b, c: None
        self.exit_application: [Callable[[], None]] = [lambda: None]

    def change_read_register_address(self, address: str):
        self.read_register_address_str = address

    def device_address_changed(self, device_address: str):
        if device_address != "":
            self.device_address = int(device_address, 16)

    @property
    def i2c(self) -> Optional[I2CMaster]:
        return self._i2c_driver

    def set_port(self, new_port: str | None) -> None:
        if self.port != new_port:
            self.port = new_port if len(new_port) > 0 else None
            if self.port is None:
                self._i2c_driver = DummyI2CMaster()
            else:
                self._i2c_driver = I2CMasterI2CDriver(I2CDriver(self.port))
                for c in self.i2c_master_changed:
                    c(self._i2c_driver)

    def scan(self) -> list[int]:
        return [] if self.i2c is None else self.i2c.scan()

    def read_register(self) -> None:
        def get_reg_addr():
            try:
                return int(self.read_register_address_str, 16)
            except ValueError:
                self.show_error("Register address is not a hex number")
                return None

        reg_addr = get_reg_addr()
        if reg_addr is not None:
            self.read_register_at_addr(reg_addr)

    def read_register_at_addr(self, reg_addr: int) -> None:
        try:
            regval = self.i2c.read_register(self.device_address, reg_addr)
            if regval is None:
                self.show_error(f"Failed to read register at address 0x{reg_addr:X}")
            else:
                self.show_read_register_results(f"0x{reg_addr:02X}", f"0x{regval.uint:02X}", regval.bin)
        except Exception as ex:
            self.show_error(f"{ex}")
