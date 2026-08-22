from collections.abc import Callable
from enum import Enum

from bitstring import BitArray
from i2c_api import I2CLogger, I2CMaster
from i2c_api.log import I2CTransactionElement
from i2capi_i2cdriver import I2CMasterI2CDriver
from i2cdriver import I2CDriver
from PySide6.QtWidgets import QApplication, QMainWindow
from rgscore import Register
from sprats.collections import Variable
from sprats.config import AppPersistence

from i2cdgui.dummy_i2cmaster import DummyI2CMaster
from i2cdgui.i2c_op_thread import HighlightOff, I2COpThread, ReadRegister, WriteRegister
from i2cdgui.project import Projects
from i2cdgui.reg_read_results import ShowRegSignalData


class InAppI2CLogger(I2CLogger):
    def __init__(self, message_appender: Callable[[list], None]):
        self.message_appender = message_appender

    def log_message(self, message: list[I2CTransactionElement]):
        self.message_appender(message)


class Foo(Enum):
    A = (1,)
    B = 2
    C = 8


Variable(Foo.A, name="state", valid_values=[Foo.A, Foo.B, Foo.C])


class App:
    def __init__(self, persistence: AppPersistence, q_application: QApplication):
        self._i2c_driver: I2CMaster | None = None
        self.port: str | None = None
        self.persistence = persistence
        self.q_application = q_application
        self.i2c_logger = InAppI2CLogger(self.append_i2c_log_message)
        self.i2c_master_changed: list[Callable[[I2CMaster], None]] = []

        self.device_address: int = -1
        self.read_register_num_bytes: Variable[int] = Variable(1, valid_values=[1, 2, 3, 4])
        self.read_register_address_str = Variable[str]("")

        self.write_register_address_str = Variable[str]("")
        self.write_register_value_str = Variable[str]("")
        self.write_register_num_bytes = Variable[int](1, valid_values=[1, 2, 3, 4])

        self.show_error: Callable[[str], None] = lambda _: None

        self.show_read_register_results: Callable[[str, str, str, bool], None] = lambda a, b, c, d: None
        self.exit_application: list[Callable[[], None]] = [lambda: None]
        self.re_read_all_period_millis: int = -1
        self.toggle_reloading_label_highlight: Callable[[], None] = lambda: None
        self.reloading_label_highlight_off: Callable[[], None] = lambda: None
        self.update_project_selector_current_project: Callable[[str], None] = lambda _: None
        self.request_results_reload: Callable[[], None] = lambda: None
        self.request_reglist_reload: Callable[[], None] = lambda: None
        self.request_reglist_select_register: Callable[[Register], None] = lambda _: None
        self.show_last_i2c_log_message: Callable[[list], None] = lambda _: None

        # called by results panel when register is read and result are (re)displayed
        self.registers_values_changed: Callable[[int], None] = lambda _: None

        self.append_custom_commands_log_stdout: Callable[[str], None] = lambda _: None
        self.request_commands_reload: Callable[[], None] = lambda: None

        self.op_thread = I2COpThread()
        self.op_thread.start()

        last_open_project_name = persistence.config.get_value("last_open_project", str)
        self.projects = Projects(persistence.config.app_name_config_dir / "projects")

        # switch to project "default" if currently listed one no longer exist
        all_available_projects = self.projects.list_projects()
        if last_open_project_name not in all_available_projects:
            last_open_project_name = "default"

        if last_open_project_name == "default" and "default" not in all_available_projects:
            # create "default" project if it does not exit
            self.projects.new_project("default")

        self.project = self.projects.open_project(last_open_project_name)
        self._main_window = None

    def append_i2c_log_message(self, log_message: list[I2CTransactionElement]):
        self.show_last_i2c_log_message(log_message)

    def connect_show_error(self, show_error: Callable[[str], None]):
        self.op_thread.show_error.connect(show_error)

    def connect_show_register_value(self, show_register_value: Callable[[ShowRegSignalData], None]):
        self.op_thread.show_register_value.connect(show_register_value)

    def connect_highlight_register_at_addr(self, highlight_register_at_addr: Callable[[str], None]):
        self.op_thread.highlight_register_at_addr.connect(highlight_register_at_addr)

    def connect_re_read_all_registers(self, re_read_all_registers: Callable[[], None]):
        self.op_thread.request_re_read_all_registers.connect(re_read_all_registers)

    def connect_highlight_off(self, highlight_off: Callable[[], None]):
        self.op_thread.request_highlight_off.connect(highlight_off)

    def device_address_changed(self, device_address: str):
        if device_address != "":
            self.device_address = int(device_address, 16)

    @property
    def main_window(self) -> QMainWindow:
        return self._main_window

    @property
    def i2c(self) -> I2CMaster | None:
        return self._i2c_driver

    def set_port(self, new_port: str | None) -> None:
        if self.port != new_port:
            self.port = new_port if len(new_port) > 0 else None
            if self.port is None:
                self._i2c_driver = DummyI2CMaster()
            else:
                self._i2c_driver = I2CMasterI2CDriver(I2CDriver(self.port), logger=self.i2c_logger)
                self.op_thread._i2c_driver = self._i2c_driver
                for c in self.i2c_master_changed:
                    c(self._i2c_driver)

    def scan(self) -> list[int]:
        return [] if self.i2c is None else self.i2c.scan()

    @staticmethod
    def get_address_width(register_address_str: str) -> int:
        register_address_len = len(register_address_str)
        return int(register_address_len / 2) + (register_address_len % 2)

    def read_register(self) -> None:
        def get_reg_addr() -> tuple[int, int] | None:
            register_address_str = self.read_register_address_str.value.strip().removeprefix("0x")
            if register_address_str == "":
                self.show_error("Register address is empty")
                return None
            else:
                try:
                    return int(register_address_str, 16), App.get_address_width(register_address_str)
                except ValueError:
                    self.show_error("Register address is not a hex number")
                    return None

        reg_addr = get_reg_addr()
        if reg_addr is not None:
            self.op_thread.commands.put(
                ReadRegister(
                    device_address=self.device_address,
                    register_address=reg_addr[0],
                    address_bus_width_in_bytes=reg_addr[1],
                    num_bytes=self.read_register_num_bytes.value,
                    highlight=True,
                )
            )
            self.op_thread.commands.put(HighlightOff(delay_millis=300))

    def write_register(self):
        register_value_str = self.write_register_value_str.value.strip()

        def get_reg_addr() -> tuple[int, int] | None:
            reg_address_str = self.write_register_address_str.value.strip().removeprefix("0x")
            if reg_address_str == "":
                self.show_error("Register address is empty")
                return None
            else:
                try:
                    return int(reg_address_str, 16), App.get_address_width(reg_address_str)
                except ValueError:
                    self.show_error("Register address is not a hex number")
                    return None

        def get_reg_value() -> BitArray | None:
            if register_value_str == "":
                self.show_error("Register value is empty")
                return None
            else:
                try:
                    if register_value_str.startswith(("0b", "0x")):
                        retval = BitArray(register_value_str)

                        write_num_bits = self.write_register_num_bytes.value * 8
                        if retval.len < write_num_bits:
                            return BitArray(write_num_bits - retval.len) + retval
                        else:
                            return retval[-write_num_bits:]
                    else:
                        raise ValueError()
                except ValueError:
                    self.show_error("Register value is not a hex or a binary number")
                    return None

        target_register_address = get_reg_addr()
        if target_register_address is None:
            return

        target_register_value = get_reg_value()
        if target_register_value is None:
            return

        self.op_thread.commands.put(
            WriteRegister(
                device_address=self.device_address,
                register_address=target_register_address[0],
                address_bus_width_in_bytes=target_register_address[1],
                register_value=target_register_value,
            )
        )
        self.op_thread.commands.put(HighlightOff(delay_millis=300))

    def re_read_register_at_addr(
        self,
        *,
        reg_addr: int,
        address_bus_width_in_bytes: int,
        num_bytes: int,
        highlight: bool = True,
    ) -> None:
        if self.device_address == -1:
            self.show_error("Please select device address to read registers from")
        else:
            self.op_thread.commands.put(
                ReadRegister(
                    device_address=self.device_address,
                    register_address=reg_addr,
                    address_bus_width_in_bytes=address_bus_width_in_bytes,
                    num_bytes=num_bytes,
                    highlight=highlight,
                )
            )
            self.op_thread.commands.put(HighlightOff(delay_millis=300))

    def init(self):
        self.update_project_selector_current_project(self.project.name)

    def open_project(self, name: str):
        self.project.save()  # save all data associated with the currently open project
        self.project = self.projects.open_project(name)
        self.request_results_reload()
        self.request_reglist_reload()
        self.request_commands_reload()
        self.update_project_selector_current_project(self.project.name)
        self.persistence.config.set_value("last_open_project", name)

    def create_new_project(self, name: str):
        self.projects.new_project(name)
        self.open_project(name)

    def create_copy_of_project(self, project_to_copy: str, new_project: str):
        src_project = self.projects.open_project(project_to_copy)
        target_project = self.projects.new_project(new_project)
        src_project.copy_to(target_project)
        self.open_project(target_project.name)

    def delete_project(self, projects_to_delete: str):
        if projects_to_delete == "default":
            self.show_error(f"Project [{projects_to_delete}] cannot be deleted.")
        else:
            self.projects.delete_project(projects_to_delete)
            project_to_open_instead = self.projects.list_projects()[0]
            self.open_project(project_to_open_instead)

    def update_results_display_data(self):
        for row in self.project.results:
            register: Register | None = self.project.reg_list.get_register_by_address(row.address)
            if register is None:
                row.name_and_address = f"0x{row.address:0{row.address_bus_width_in_bytes * 2}X}"
            else:
                row.name_and_address = (
                    f"{register.name} @ 0x{register.address:0{register.address_bus_width_bytes * 2}X}"
                )
