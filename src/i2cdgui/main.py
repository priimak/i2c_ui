import sys
from typing import override

import serial.tools.list_ports as slp
from PySide6.QtCore import QSize, QByteArray
from PySide6.QtGui import QPalette, Qt, QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QSplitter
from pytide6 import MainWindow, set_geometry, VBoxPanel, W, HBoxPanel, ComboBox
from pytide6.palette import Palette
from sprats.config import AppPersistence

from i2cdgui.app import App
from i2cdgui.commands_panel import CommandsPanel
from i2cdgui.i2c_op_thread import Quit
from i2cdgui.menus import MainMenuBar
from i2cdgui.results_panel import ResultsPanel


def get_ports() -> list[str]:
    return [p.device for p in slp.comports() if p.product == "FT230X Basic UART"]


class COMPortSelector(ComboBox):
    def __init__(self, app: App):
        super().__init__(items=get_ports())
        self.app = app

        self.currentTextChanged.connect(self.app.set_port)
        self.currentTextChanged.emit(self.currentText())


class InfoPanel(HBoxPanel):
    def __init__(self, app: App):
        super().__init__()
        self.setPalette(Palette(QPalette.ColorRole.Window, "#f1f1f1"))
        self.setAutoFillBackground(True)

        self.com_port_selector = COMPortSelector(app)
        self.layout().addStretch(stretch=1)
        self.layout().addWidget(self.com_port_selector)


class I2CDriverWindow(MainWindow):
    def __init__(self, screen_dim: tuple[int, int], app: App):
        super().__init__(objectName="MainWindow", windowTitle="I2CDriver GUI")

        self.setStyleSheet("QMainWindow { background-color: #ffffff; }")
        set_geometry(app_state=app.persistence.state, widget=self, screen_dim=screen_dim, win_size_fraction=0.7)

        self.app = app
        self.info_panel = InfoPanel(app)

        # if self.info_panel.com_port_selector.count() == 0:
        #     self.show_error("I2C Master device not found")

        self.hsplitter = QSplitter(Qt.Orientation.Horizontal)
        self.hsplitter.setChildrenCollapsible(False)
        self.hsplitter.setHandleWidth(8)

        self.res_table = ResultsPanel(self.app)
        left_panel = VBoxPanel(widgets=[self.res_table], background_color="gray", margins=1)
        self.hsplitter.addWidget(left_panel)

        cpanel = CommandsPanel(app)
        cpanel.setBackgroundColor("orange")
        right_panel = VBoxPanel(widgets=[
            VBoxPanel([cpanel], background_color="black", margins=1), W(VBoxPanel(background_color="pink"), stretch=2)
        ], margins=0)
        self.hsplitter.addWidget(right_panel)
        self.setCentralWidget(
            VBoxPanel(
                widgets=[W(HBoxPanel(widgets=[self.hsplitter]), stretch=2), self.info_panel],
                spacing=0, margins=(0, 0, 0, 0)
            )
        )

        app.show_error = self.show_error
        app.connect_show_error(self.show_error)
        app.connect_show_register_value(self.res_table.show_register_value)

        self.main_menu_bar = self.setMenuBar(MainMenuBar(self.app, dialogs_parent=self))
        self.app.exit_application[0] = self.exit_application

    def exit_application(self):
        self.app.op_thread.commands.put(Quit())
        self.close()

    @override
    def closeEvent(self, event: QCloseEvent):
        self.app.persistence.state.save_geometry(self.objectName(), self.saveGeometry())

        state: QByteArray = self.hsplitter.saveState()
        spl_state = state.toBase64(QByteArray.Base64Option.Base64Encoding).data().decode("utf-8")
        self.app.persistence.state.set_value("splitter_state", spl_state)

        event.accept()

    def restore(self):
        spl_state = self.app.persistence.state.get_value("splitter_state")
        if spl_state is not None:
            self.hsplitter.restoreState(QByteArray.fromBase64(spl_state.encode("utf-8")))

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Error", message)


def main():
    app = QApplication(sys.argv)

    persistence = AppPersistence(
        app_name="i2cdgui",
        override_config_if_different_version=True,
        init_config_data={
            "speed": "100"
        }
    )

    # Will init main window size to be some fraction of the screen size unless defined elsewhere
    screen_dim: QSize = app.primaryScreen().size()
    screen_width, screen_height = screen_dim.width(), screen_dim.height()

    try:
        win = I2CDriverWindow(
            screen_dim=(screen_width, screen_height), app=App(persistence)
        )
        win.show()
        win.activateWindow()
        win.raise_()
        win.restore()
        if win.info_panel.com_port_selector.count() == 0:
            win.app.show_error("I2C Master device not found. Connect device and restart application.")

        sys.exit(app.exec())
    except Exception as ex:
        QMessageBox.critical(None, "Error", f"Error: {ex}")
        exit(1)


if __name__ == "__main__":
    main()
