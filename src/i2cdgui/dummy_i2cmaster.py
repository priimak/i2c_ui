from bitstring import Bits
from i2c_api import I2CLogger, I2CMaster
from i2capi_i2cdriver.i2cdriver_api import DummyI2CLogger


class DummyI2CMaster(I2CMaster):
    def __init__(self):
        self.__logger = DummyI2CLogger()

    def logger(self) -> I2CLogger:
        return self.__logger

    def write_register(
        self,
        address: int,
        register: int,
        data: Bits | str | int | list[int],
        num_bytes: int | None = 1,
        read_back: bool = False,
        use_restart: bool = True,
    ) -> Bits | None:
        return None

    def write(
        self,
        address: int,
        data: Bits | str | int | list[int],
        num_bytes: int | None = None,
    ) -> bool:
        return False

    def read(self, address: int, num_bytes: int = 1) -> Bits | None:
        return None

    def read_register(
        self, address: int, register: int, num_bytes: int = 1, use_restart: bool = True
    ) -> Bits | None:
        return None

    def scan(self) -> list[int]:
        return []

    def list_pullups(self) -> list[str]:
        return ["4.7K"]

    def set_pullup(self, pullup_value: str) -> None:
        pass

    def get_pullup(self) -> str:
        return ""

    def list_clk_speeds(self) -> list[int]:
        return [100]

    def get_clk_speed(self) -> int:
        return 100

    def set_clk_speed(self, speed: int) -> None:
        pass
