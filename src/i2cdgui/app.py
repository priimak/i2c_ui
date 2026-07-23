from typing import Optional

from i2cdriver import I2CDriver
from sprats.config import AppPersistence


class App:
    def __init__(self, persistence: AppPersistence):
        self._i2c_driver = None
        self.port: str | None = None
        self.persistence = persistence

    @property
    def i2c(self) -> Optional[I2CDriver]:
        return self._i2c_driver

    def set_port(self, new_port: str | None) -> None:
        if self.port != new_port:
            self.port = new_port if len(new_port) > 0 else None
            if self.port is None:
                self._i2c_driver = None
            else:
                self._i2c_driver = I2CDriver(self.port)
                regrd = self.i2c.regrd(0x40, 6)
                # print(f"regrd {regrd}")
                self.i2c.regwr(0x40, 6, 7)
                regrd = self.i2c.regrd(0x40, 6)
                # print(f"regrd {regrd}")

    def scan(self) -> list[int]:
        return [] if self.i2c is None else self.i2c.scan(silent=True)
