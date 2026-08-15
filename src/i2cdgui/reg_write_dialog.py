from PySide6.QtCore import QMargins
from PySide6.QtGui import QDoubleValidator, QFocusEvent, QKeyEvent, QPalette, Qt
from PySide6.QtWidgets import QGridLayout
from pytide6 import (
    Dialog,
    HBoxPanel,
    Label,
    Panel,
    PushButton,
    RichTextLabel,
    VBoxLayout,
    W,
)
from pytide6.frame import HorizonalLine
from pytide6.inputs import LineEdit
from rgscore import Register

from i2cdgui.app import App


class FieldValueInput(LineEdit):
    def __init__(self, text: str, register: Register, field_name: str):
        super().__init__(text, validator=QDoubleValidator())
        self.register = register
        self.field_name = field_name

    def reset_field_value_text(self):
        set_value = self.register.get_field_value(self.field_name)
        self.setText(f"{set_value}")

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        if self.text().strip() == "":
            self.reset_field_value_text()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        super().keyPressEvent(event)
        key = event.key()
        if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter] and self.text().strip() == "":
            self.reset_field_value_text()

        elif key == Qt.Key.Key_Up:
            new_field_value = self.register.get_next_up_field_value(self.field_name)
            self.setText(f"{new_field_value}")
            self.editingFinished.emit()

        elif key == Qt.Key.Key_Down:
            new_field_value = self.register.get_next_down_field_value(self.field_name)
            self.setText(f"{new_field_value}")
            self.editingFinished.emit()


class RegisterWriteDialog(Dialog):
    def __init__(self, app: App, *, register: Register):
        super().__init__(app.main_window, windowTitle="Write Register", modal=True)
        self.register = register

        layout = QGridLayout()
        layout.addWidget(Label("Name: "), 0, 0)
        layout.addWidget(
            RichTextLabel(f"<span style='color: blue;'>{register.name}</span>"), 0, 1
        )
        layout.addWidget(Label("Address: "), 1, 0)
        layout.addWidget(
            RichTextLabel(
                f"<span style='color: blue;'>0x{register.address:02X}</span>"
            ),
            1,
            1,
        )
        layout.addWidget(Label("Raw data: "), 2, 0)
        raw_data_label = RichTextLabel(
            f"<span style='color: blue;'>{register.data.bin}</span>"
        )
        layout.addWidget(raw_data_label, 2, 1)
        layout.addWidget(Label("Fields: "), 3, 0, 2, 1)

        fields_layout = QGridLayout()
        fields_layout.setColumnStretch(3, 10)
        for row, field_name in enumerate(register.get_field_names()):

            def mk_field_value_setter(fname: str, input_line_edit: LineEdit):
                def set_field_value():
                    min_val, max_val = register.get_field_definition(fname).range()
                    try:
                        actually_set_value = register.set_field_value(
                            fname,
                            max(min_val, min(max_val, float(input_line_edit.text()))),
                        )
                        input_line_edit.setText(f"{actually_set_value}")
                    except Exception:
                        current_field_value = register.get_field_value(fname)
                        input_line_edit.setText(f"{current_field_value}")
                    raw_data_label.setText(
                        f"<span style='color: blue;'>{register.data.bin}</span>"
                    )

                return set_field_value

            field_value_input_field = FieldValueInput(
                f"{register.get_field_value(field_name)}", register, field_name
            )
            field_value_input_field.editingFinished.connect(
                mk_field_value_setter(field_name, field_value_input_field)
            )

            fields_layout.addWidget(
                RichTextLabel(
                    f"<span style='color: blue;'>{field_name}&nbsp;&nbsp;</span>"
                ),
                row,
                0,
            )
            field_definition = register.get_field_definition(field_name)
            if not field_definition.rw:
                field_value_input_field.setEnabled(False)
            fields_layout.addWidget(
                Label(f"[{field_definition.end_offset()}:{field_definition.offset}]  "),
                row,
                1,
            )
            fields_layout.addWidget(
                Label(
                    f"{field_definition.signed}{field_definition.width}.{field_definition.fractional}  "
                ),
                row,
                2,
            )
            fields_layout.addWidget(
                Label("rw" if field_definition.rw else "ro"), row, 3
            )
            fields_layout.addWidget(field_value_input_field, row, 4)

        fields_panel = Panel(fields_layout)
        fields_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        layout.addWidget(fields_panel, 5, 1)

        layout.setColumnStretch(1, 10)

        self.setLayout(
            VBoxLayout(
                [
                    Panel(layout, background_color="white"),
                    W(stretch=1),
                    HorizonalLine(),
                    HBoxPanel(
                        [
                            W(stretch=1),
                            PushButton("Ok", auto_default=False),
                            PushButton(
                                "Cancel", on_clicked=self.close, auto_default=False
                            ),
                        ]
                    ),
                ]
            )
        )

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, "white")
        self.setAutoFillBackground(True)
        self.setPalette(palette)
