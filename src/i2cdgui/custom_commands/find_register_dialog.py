from PySide6 import QtCore
from pytide6 import Dialog, Label, VBoxLayout

from i2cdgui.app import App


class FindRegisterDialog(Dialog):
    def __init__(self, parent, app: App):
        super().__init__(parent, windowTitle="Find Register", modal=True)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Window
        )
        self.setStyleSheet(
            "QDialog { background-color: #DDDDFF; border: 1px solid black; }"
        )
        self.setLayout(VBoxLayout([Label("Registers")], margins=3))
