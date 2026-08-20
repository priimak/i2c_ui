import dataclasses
import traceback

from PySide6 import QtCore
from PySide6.QtGui import QKeyEvent, Qt
from PySide6.QtWidgets import QTextEdit
from pytide6 import Dialog, HBoxPanel, PushButton, VBoxLayout, W
from pytide6.frame import HorizonalLine
from pytide6.inputs import LineEdit
from sprats.collections import Variable

from i2cdgui.app import App
from i2cdgui.project import CustomCommand


class CodeEditor(QTextEdit):
    space_key_event = QKeyEvent(QtCore.QEvent.Type.KeyPress, Qt.Key.Key_A, QtCore.Qt.KeyboardModifier.NoModifier, " ")

    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.setStyleSheet("QTextEdit { font-family: 'Monospace'; }")
        char_width = self.fontMetrics().height()
        self.setMinimumHeight(char_width * 25)

    def keyPressEvent(self, event: QKeyEvent, /) -> None:
        if event.type() == QtCore.QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            super().keyPressEvent(CodeEditor.space_key_event)
            super().keyPressEvent(CodeEditor.space_key_event)
            super().keyPressEvent(CodeEditor.space_key_event)
            super().keyPressEvent(CodeEditor.space_key_event)
        else:
            super().keyPressEvent(event)

        # if event.key() == Qt.Key.Key_Period:
        #     pos = self.cursorRect().topLeft()
        #     pos = self.viewport().mapToGlobal(pos)
        #     dialog = FindRegisterDialog(self, self.app)
        #     dialog.move(pos)
        #     dialog.exec()
        #
        #     QToolTip.showText(pos, "Hello there")


class CustomCommandsEditor(Dialog):
    def __init__(self, app: App, cmd: CustomCommand | None):
        super().__init__(app.main_window, windowTitle="Edit/Create Custom Command", modal=True)
        self.app = app
        self.original_cmd = None if cmd is None else dataclasses.replace(cmd)

        self.command_label = Variable("" if cmd is None else cmd.label)
        self.code_editor = CodeEditor(app)
        if cmd is not None:
            self.code_editor.append(cmd.source_code)

        self.setLayout(
            VBoxLayout(
                [
                    LineEdit(
                        reactive_variable=self.command_label,
                        with_min_width_for_text=(" " * 200),
                    ),
                    W(self.code_editor, stretch=1),
                    HorizonalLine(),
                    HBoxPanel(
                        [
                            W(stretch=1),
                            PushButton("Ok", on_clicked=self.save_command, auto_default=False),
                            PushButton("Cancel", on_clicked=self.close, auto_default=False),
                        ],
                        margins=0,
                    ),
                ]
            )
        )

    def save_command(self):
        code = self.code_editor.toPlainText()
        try:
            if self.original_cmd is None and self.command_label.value in self.app.project.commands_by_label:
                self.app.show_error("Command with this label already exist. Please pick another label.")
                return

            new_cmd = CustomCommand(
                label=self.command_label.value,
                source_code=code,
                compiled_code=compile(code, "<str>", "exec"),
            )
            if self.original_cmd is None:
                self.app.project.add_custom_command(new_cmd)
            else:
                self.app.project.update_custom_command(self.original_cmd, new_cmd)

            self.close()
            self.app.request_commands_reload()
        except Exception as ex:
            tb_lines = traceback.format_exception(type(ex), ex, ex.__traceback__)
            x = "".join(tb_lines[2:])
            self.app.show_error(str(x))

        # CONFIG.a_en = 1
