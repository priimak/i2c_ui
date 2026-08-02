from collections.abc import Callable

from i2c_api import I2CMaster
from i2capi_i2cdriver import I2CMasterI2CDriver
from i2cdriver import I2CDriver
from PySide6.QtWidgets import QApplication, QMainWindow
from sprats.config import AppPersistence

from i2cdgui.dummy_i2cmaster import DummyI2CMaster
from i2cdgui.i2c_op_thread import HighlightOff, I2COpThread, ReadRegister
from i2cdgui.project import Projects
from i2cdgui.reg_read_results import ShowRegSignalData


class App:
    def __init__(self, persistence: AppPersistence, q_application: QApplication):
        self._i2c_driver: I2CMaster | None = None
        self.port: str | None = None
        self.persistence = persistence
        self.q_application = q_application
        self.i2c_master_changed: list[Callable[[I2CMaster], None]] = []

        self.device_address: int = -1
        self.read_register_num_bytes: int = 1
        self.read_register_address_str = ""

        self.write_register_num_bytes: int = 1
        self.show_error: Callable[[str], None] = lambda _: None

        self.show_read_register_results: Callable[[str, str, str, bool], None] = (
            lambda a, b, c, d: None
        )
        self.exit_application: list[Callable[[], None]] = [lambda: None]
        self.re_read_all_period_millis: int = -1
        self.toggle_reloading_label_highlight: Callable[[], None] = lambda: None
        self.reloading_label_highlight_off: Callable[[], None] = lambda: None
        self.update_project_selector_current_project: Callable[[str], None] = lambda _: (
            None
        )
        self.project_names_changed: Callable[[list[str]], None] = lambda _: None
        self.request_results_reload: Callable[[], None] = lambda: None

        self.op_thread = I2COpThread()
        self.op_thread.start()

        last_open_project_name = persistence.config.get_value("last_open_project", str)
        self.projects = Projects(persistence.config.app_name_config_dir / "projects")

        # switch to project "default" if currently listed one no longer exist
        all_available_projects = self.projects.list_projects()
        if last_open_project_name not in all_available_projects:
            last_open_project_name = "default"

        if (
            last_open_project_name == "default"
            and "default" not in all_available_projects
        ):
            # create "default" project if it does not exit
            self.projects.new_project("default")

        self.project = self.projects.open_project(last_open_project_name)
        self._main_window = None

    def connect_show_error(self, show_error: Callable[[str], None]):
        self.op_thread.show_error.connect(show_error)

    def connect_show_register_value(
        self, show_register_value: Callable[[ShowRegSignalData], None]
    ):
        self.op_thread.show_register_value.connect(show_register_value)

    def connect_highlight_register_at_addr(
        self, highlight_register_at_addr: Callable[[str], None]
    ):
        self.op_thread.highlight_register_at_addr.connect(highlight_register_at_addr)

    def connect_re_read_all_registers(self, re_read_all_registers: Callable[[], None]):
        self.op_thread.request_re_read_all_registers.connect(re_read_all_registers)

    def connect_highlight_off(self, highlight_off: Callable[[], None]):
        self.op_thread.request_highlight_off.connect(highlight_off)

    def change_read_register_address(self, address: str):
        self.read_register_address_str = address

    def change_read_register_num_bytes(self, num_bytes: str):
        self.read_register_num_bytes = int(num_bytes)

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
                self._i2c_driver = I2CMasterI2CDriver(I2CDriver(self.port))
                self.op_thread._i2c_driver = self._i2c_driver
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
            self.op_thread.commands.put(
                ReadRegister(
                    self.device_address,
                    reg_addr,
                    num_bytes=self.read_register_num_bytes,
                    highlight=True,
                )
            )
            self.op_thread.commands.put(HighlightOff(delay_millis=300))

    def re_read_register_at_addr(
        self, reg_addr: int, num_bytes: int, highlight: bool = True
    ) -> None:
        if self.device_address == -1:
            self.show_error("Please select device address to read registers from")
        else:
            self.op_thread.commands.put(
                ReadRegister(
                    device_address=self.device_address,
                    register_address=reg_addr,
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
        self.update_project_selector_current_project(self.project.name)
        self.persistence.config.set_value("last_open_project", name)
        self.project_names_changed(self.projects.list_projects())

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
