from PySide6.QtWidgets import QMenu, QMenuBar, QMessageBox, QWidget

from i2cdgui import __version__
from i2cdgui.app import App
from i2cdgui.find_actions_dialog import FindActionDialog
from i2cdgui.projects_gui import (
    DeleteProjectDialog,
    NewProjectDialog,
    OpenProjectDialog,
    SaveAsProjectDialog,
)


class FileMenu(QMenu):
    def __init__(self, parent: QMenuBar, app: App):
        super().__init__("&File", parent)

        def show_settings_window():
            pass

        def export_project():
            pass

        def import_project():
            pass

        def delete_project():
            if app.project.name == "default":
                app.show_error(f"Project [{app.project.name}] cannot be deleted.")
                app.update_project_selector_current_project(app.project.name)
            else:
                DeleteProjectDialog(app, app.project.name).exec()

        self.addAction("&New Project", lambda: NewProjectDialog(app).exec())
        self.addAction("&Save As Project", lambda: SaveAsProjectDialog(app).exec())
        self.addAction("&Open Project", lambda: OpenProjectDialog(app).exec())
        self.addAction("&Delete Project", delete_project)
        self.addSeparator()
        self.addAction("&Export Project", export_project)
        self.addAction("&Import Project", import_project)
        self.addSeparator()
        self.addAction("S&ettings", show_settings_window)
        self.addSeparator()
        self.addAction("&Quit", lambda: app.exit_application[0]())


class HelpMenu(QMenu):
    def __init__(self, parent: QWidget, app: App):
        super().__init__("&Help", parent)

        self.addAction(
            "Find Action... Ctrl+Shift+A", lambda: FindActionDialog(app).exec()
        )
        self.addAction(
            "&About",
            lambda: QMessageBox.about(
                parent,
                "About",
                f"<html><H2>I2C GUI</H2><H4>Version: {__version__}</H4>"
                '<p style="font-size:14px;">"While there is life there is hope. I beg to assert...that '
                "as long as a man's heart beats, as long as a man's flesh quivers, I do not allow that a being "
                'gifted with thought and will can allow himself to despair."</br>'
                "&nbsp;&nbsp;&nbsp;&nbsp;- <em>Jules Verne, Journey to the Center of the Earth</em></html>",
            ),
        )


class MainMenuBar(QMenuBar):
    def __init__(self, app: App, dialogs_parent: QWidget) -> None:
        super().__init__(dialogs_parent)
        self.addMenu(FileMenu(self, app))
        self.addMenu(HelpMenu(self, app))
