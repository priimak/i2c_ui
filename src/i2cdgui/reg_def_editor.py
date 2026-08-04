import re
from collections.abc import Callable

from PySide6 import QtGui
from PySide6.QtCore import Qt
from PySide6.QtGui import QRegularExpressionValidator, Qt
from PySide6.QtWidgets import QFrame, QWidget
from pytide6 import (
    CheckBox,
    ComboBox,
    Dialog,
    HBoxPanel,
    Label,
    PushButton,
    VBoxLayout,
    VBoxPanel,
    W,
)
from pytide6.inputs import LineEdit
from rgscore import FieldDef, Register

from i2cdgui.app import App


class AddressInput(LineEdit):
    valid_address_re = re.compile("^(0x)?[0-9a-fA-F]+$]]")

    def __init__(self, register: Register, set_address_func: Callable[[str], None]):
        super().__init__(
            text="" if register.address is None else f"0x{register.address:04X}",
            with_fixed_width_for_text="0xFFFF",
            validator=QRegularExpressionValidator("^(0x)?[0-9a-fA-F]{0,4}$"),
            on_text_change=set_address_func,
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def reformat_input_text(self):
        entered_address = self.text().strip()
        if re.match("^(0x)?[0-9a-fA-F]{1,4}$", entered_address):
            address = int(self.text(), 16)
            self.setText(f"0x{address:04X}")

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.reformat_input_text()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Return:
            self.reformat_input_text()

        super().keyPressEvent(event)


class DefRegEditor(Dialog):
    def __init__(self, app: App, *, windowTitle: str | None = None):
        super().__init__(app.main_window, windowTitle=windowTitle, modal=True)
        self.app = app
        self.register = Register(
            8,
            name=None,
            model=[
                FieldDef.value_of("field_name@[7:0]U8.0#rw"),
            ],
        )
        name = "" if self.register.name is None else self.register.name
        self.register.width = 8 * (self.register.width // 8) + (
            8 if (self.register.width % 8) > 0 else 0
        )
        self.new_register_address = ""

        def set_new_register_address(addr: str):
            self.new_register_address = addr

        self.fields_panel = VBoxPanel(margins=0)
        self.build_fields_panel()

        def mk_line():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            return line

        self.setLayout(
            VBoxLayout(
                [
                    HBoxPanel(
                        [
                            Label("Register Name"),
                            LineEdit(
                                name,
                                on_text_change=self.register.set_name,
                                with_fixed_width_for_text="Very Long Register Name",
                            ),
                            Label("  Addr"),
                            AddressInput(
                                self.register, set_address_func=set_new_register_address
                            ),
                            Label("  Width"),
                            ComboBox(
                                items=["8", "16", "24", "32"],
                                current_selection=f"{self.register.width}",
                            ),
                            W(QWidget(), stretch=1),
                        ],
                        margins=0,
                    ),
                    mk_line(),
                    self.fields_panel,
                    W(QWidget(), stretch=1),
                    mk_line(),
                    HBoxPanel(
                        [
                            W(QWidget(), stretch=1),
                            PushButton("Ok", on_clicked=self.save_register),
                            PushButton("Cancel", on_clicked=self.close),
                        ],
                        margins=0,
                    ),
                ]
            )
        )

    def save_register(self):
        if self.register.name is None or self.register.name.strip() == "":
            self.app.show_error("Register must have a name")
        elif not Register.register_name_re.match(self.register.name):
            self.app.show_error(
                "Register name must not be empty and contain only numbers, letters and (_) underscores."
            )
        elif self.new_register_address.strip() in ["", "0x"]:
            self.app.show_error("Register must have an address")

    def build_fields_panel(self):
        layout: VBoxLayout = self.fields_panel.layout()
        wgs = [
            HBoxPanel(
                [Label("Fields"), PushButton("Add New Field"), W(QWidget(), stretch=1)],
                margins=0,
            )
        ]
        for field_name in self.register.get_field_names():
            field_def = self.register.get_field_definition(field_name)

            cbs = [
                CheckBox(
                    checked=(i >= field_def.offset and i <= field_def.end_offset())
                )
                for i in range(self.register.width)[::-1]
            ]
            field_width_label = Label(f"{field_def.width}.")

            fractional_input = LineEdit(
                f"{field_def.fractional}", with_fixed_width_for_text="00"
            )

            wgs.append(
                HBoxPanel(
                    cbs
                    + [
                        Label(" "),
                        LineEdit(
                            field_def.name,
                            with_fixed_width_for_text="Very Long Field Name",
                        ),
                        ComboBox(
                            items=["rw", "ro"],
                            current_selection="rw" if field_def.rw else "ro",
                        ),
                        ComboBox(
                            items=["Unsinged", "Signed"],
                            current_selection=(0 if field_def.signed == "U" else 1),
                        ),
                        field_width_label,
                        fractional_input,
                        Label("  "),
                        W(QWidget(), stretch=1),
                        PushButton("Delete"),
                    ],
                    margins=0,
                )
            )
        layout.addWidgets(wgs)
