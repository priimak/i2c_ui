import sys
from typing import override

import serial.tools.list_ports as slp
from PySide6 import QtGui
from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QCloseEvent, QPalette, Qt
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QSplitter
from pytide6 import ComboBox, HBoxPanel, MainWindow, VBoxPanel, W, set_geometry
from pytide6.palette import Palette
from sprats.config import AppPersistence

from i2cdgui.app import App
from i2cdgui.commands_panel import CommandsPanel
from i2cdgui.i2c_op_thread import Quit
from i2cdgui.menus import MainMenuBar
from i2cdgui.projects_gui import (
    DeleteProjectDialog,
    NewProjectDialog,
    OpenProjectDialog,
)
from i2cdgui.results_panel import ResultsPanel


def get_ports() -> list[str]:
    return [p.device for p in slp.comports() if p.product == "FT230X Basic UART"]


class COMPortSelector(ComboBox):
    def __init__(self, app: App):
        super().__init__(items=get_ports())
        self.app = app

        self.currentTextChanged.connect(self.app.set_port)
        self.currentTextChanged.emit(self.currentText())


# class ProjectSelector(ComboBox):
#     def __init__(self, app: App):


class InfoPanel(HBoxPanel):
    def __init__(self, app: App):
        super().__init__()
        self.setPalette(Palette(QPalette.ColorRole.Window, "#f1f1f1"))
        self.setAutoFillBackground(True)

        self.com_port_selector = COMPortSelector(app)
        # opened_project_label = QLabel("Project: ?")
        # self.layout().addWidget(opened_project_label)

        available_projects = app.projects.list_projects()
        projects_selector = ComboBox(
            items=["New Project", "Open Project", "Delete Project"]
            + available_projects[0:10]
            + ["..."]
        )
        projects_selector.insertSeparator(3)

        dispatch_projects_selector_update = [True]

        def projects_selector_dispatcher(_):
            if dispatch_projects_selector_update[0]:
                match projects_selector.currentText():
                    case "New Project":
                        NewProjectDialog(app).exec()
                    case "Open Project" | "...":
                        OpenProjectDialog(app).exec()
                    case "Delete Project":
                        if app.project.name == "default":
                            app.show_error(
                                f"Project [{app.project.name}] cannot be deleted."
                            )
                            app.update_project_selector_current_project(
                                app.project.name
                            )
                        else:
                            DeleteProjectDialog(app, app.project.name).exec()
                    case project_name:
                        if project_name != "" and project_name != app.project.name:
                            app.open_project(project_name)

        projects_selector.currentTextChanged.connect(projects_selector_dispatcher)

        self.layout().addWidget(QLabel("Project:"))
        self.layout().addWidget(projects_selector)

        self.layout().addStretch(stretch=1)
        self.layout().addWidget(self.com_port_selector)

        def update_project_selector_current_project(project_name: str):
            if (
                dispatch_projects_selector_update[0]
                and projects_selector.currentText() != project_name
            ):
                projects_selector.setCurrentText(project_name)

        app.update_project_selector_current_project = (
            update_project_selector_current_project
        )

        def reconstruct_list_of_projects(projects: list[str]):
            try:
                dispatch_projects_selector_update[0] = False
                projects_selector.clear()
                projects_selector.addItems(
                    ["New Project", "Open Project", "Delete Project"]
                    + projects[0:10]
                    + ["..."]
                )
                projects_selector.setCurrentText(app.project.name)
                projects_selector.insertSeparator(3)
            finally:
                dispatch_projects_selector_update[0] = True

        app.project_names_changed = reconstruct_list_of_projects


class I2CDriverWindow(MainWindow):
    def __init__(self, screen_dim: tuple[int, int], app: App):
        super().__init__(objectName="MainWindow", windowTitle="I2CDriver GUI")

        self.setStyleSheet("QMainWindow { background-color: #ffffff; }")
        set_geometry(
            app_state=app.persistence.state,
            widget=self,
            screen_dim=screen_dim,
            win_size_fraction=0.7,
        )

        self.app = app
        self.info_panel = InfoPanel(app)

        # if self.info_panel.com_port_selector.count() == 0:
        #     self.show_error("I2C Master device not found")

        self.hsplitter = QSplitter(Qt.Orientation.Horizontal)
        self.hsplitter.setChildrenCollapsible(False)
        self.hsplitter.setHandleWidth(8)

        self.res_table = ResultsPanel(self.app)
        left_panel = VBoxPanel(
            widgets=[self.res_table], background_color="gray", margins=1
        )
        self.hsplitter.addWidget(left_panel)

        cpanel = CommandsPanel(app)
        cpanel.setBackgroundColor("orange")
        right_panel = VBoxPanel(
            widgets=[
                VBoxPanel([cpanel], background_color="black", margins=1),
                W(VBoxPanel(background_color="pink"), stretch=2),
            ],
            margins=0,
        )
        self.hsplitter.addWidget(right_panel)
        self.setCentralWidget(
            VBoxPanel(
                widgets=[
                    W(HBoxPanel(widgets=[self.hsplitter]), stretch=2),
                    self.info_panel,
                ],
                spacing=0,
                margins=(0, 0, 0, 0),
            )
        )

        app.show_error = self.show_error
        app.connect_show_error(self.show_error)
        app.connect_show_register_value(self.res_table.show_register_value)

        self.main_menu_bar = self.setMenuBar(MainMenuBar(self.app, dialogs_parent=self))
        self.app.exit_application[0] = self.exit_application

    def keyPressEvent(self, event: QtGui.QKeyEvent, /) -> None:
        if (
            event.key() == Qt.Key.Key_A
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ):
            print(f"keyPressEvent {event}")
            # TODO: Add code to show list of commands
        super().keyPressEvent(event)

    def exit_application(self):
        self.close()

    @override
    def closeEvent(self, event: QCloseEvent):
        self.app.op_thread.commands.put(Quit())
        self.app.persistence.state.save_geometry(self.objectName(), self.saveGeometry())

        state: QByteArray = self.hsplitter.saveState()
        spl_state = (
            state.toBase64(QByteArray.Base64Option.Base64Encoding)
            .data()
            .decode("utf-8")
        )
        self.app.persistence.state.set_value("splitter_state", spl_state)
        self.app.project.save()
        event.accept()

    def restore(self):
        spl_state = self.app.persistence.state.get_value("splitter_state")
        if spl_state is not None:
            self.hsplitter.restoreState(
                QByteArray.fromBase64(spl_state.encode("utf-8"))
            )

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Error", message)


def main():
    app = QApplication(sys.argv)

    persistence = AppPersistence(
        app_name="i2cdgui",
        override_config_if_different_version=True,
        init_config_data={
            "speed": "100",
            "config_version": 1,
            "last_open_project": "default",
        },
    )

    # Will init main window size to be some fraction of the screen size unless defined elsewhere
    screen_dim: QSize = app.primaryScreen().size()
    screen_width, screen_height = screen_dim.width(), screen_dim.height()

    try:
        application = App(persistence)
        win = I2CDriverWindow(screen_dim=(screen_width, screen_height), app=application)
        application._main_window = win
        win.show()
        win.activateWindow()
        win.raise_()
        win.restore()
        if win.info_panel.com_port_selector.count() == 0:
            win.app.show_error(
                "I2C Master device not found. Connect device and restart application."
            )
        application.init()

        sys.exit(app.exec())
    except Exception as ex:
        QMessageBox.critical(None, "Error", f"Error: {ex}")
        sys.exit(1)


if __name__ == "__main__":
    main()
