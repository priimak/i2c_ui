from PySide6.QtWidgets import QMenu, QMenuBar, QMessageBox, QWidget
from i2cdgui import __version__
from i2cdgui.app import App


class FileMenu(QMenu):
    def __init__(self, parent: QMenuBar, app: App):
        super().__init__("&File", parent)

        def show_settings_window():
            pass

        self.addAction("&New Project", show_settings_window)
        self.addAction("&Save As Project", show_settings_window)
        self.addAction("&Open Project", show_settings_window)
        self.addSeparator()
        self.addAction("&Settings", show_settings_window)
        self.addSeparator()
        self.addAction("&Quit", lambda: app.exit_application[0]())


class HelpMenu(QMenu):
    def __init__(self, parent: QMenuBar):
        super().__init__("&Help", parent)

        # In QMessageBox.about(parent = None, ...) will place message window at the center of the screen
        self.addAction(  # pyright: ignore [reportCallIssue]
            "&About",
            lambda: QMessageBox.about(
                None,  # pyright: ignore [reportArgumentType]
                "About",
                f"<html><H2>I2C GUI</H2><H4>Version: {__version__}</H4><br/>"
                "<p style=\"font-size:14px;\">“We are at the very beginning of time for the human race. "
                "It is not unreasonable that we grapple with problems. But there are tens of thousands of "
                "years in the future. Our responsibility is to do what we can, learn what we can, improve "
                "the solutions, and pass them on.”  "
                "</br>&nbsp;&nbsp;&nbsp;&nbsp;- <em>Richard P. Feynman </em></p></html>"
            )
        )


class MainMenuBar(QMenuBar):
    def __init__(self, app: App, dialogs_parent: QWidget) -> None:
        super().__init__(dialogs_parent)
        self.addMenu(FileMenu(self, app))
        self.addMenu(HelpMenu(self))
