from collections.abc import Callable

from PySide6 import QtCore
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import (
    QDoubleValidator,
    QFocusEvent,
    QKeyEvent,
    QPalette,
)
from PySide6.QtWidgets import QGridLayout, QStyle, QToolButton
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
    def __init__(self, parent, text: str, register: Register, field_name: str):
        super().__init__(text, validator=QDoubleValidator())
        self.register = register
        self.field_name = field_name
        self.setParent(parent)

    def next_up(self):
        self.keyPressEvent(
            QKeyEvent(
                QtCore.QEvent.Type.KeyPress,
                Qt.Key.Key_Up,
                QtCore.Qt.KeyboardModifier.NoModifier,
            )
        )

    def next_down(self):
        self.keyPressEvent(
            QKeyEvent(
                QtCore.QEvent.Type.KeyPress,
                Qt.Key.Key_Down,
                QtCore.Qt.KeyboardModifier.NoModifier,
            )
        )

    def reset_field_value_text(self):
        set_value = self.register.get_field_value(self.field_name)
        self.setText(f"{set_value}")

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        if self.text().strip() == "":
            self.reset_field_value_text()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            super().keyPressEvent(event)
            self.parent().focusNextPrevChild(True)
            return

        elif key == Qt.Key.Key_Up:
            new_field_value = self.register.get_next_up_field_value(self.field_name)
            self.setText(f"{new_field_value}")
            self.editingFinished.emit()

        elif key == Qt.Key.Key_Down:
            new_field_value = self.register.get_next_down_field_value(self.field_name)
            self.setText(f"{new_field_value}")
            self.editingFinished.emit()

        super().keyPressEvent(event)


class RegisterWriteDialog(Dialog):
    def __init__(self, app: App, *, register: Register):
        super().__init__(app.main_window, windowTitle="Write Register", modal=True)
        self.app = app
        self.register = register.copy()

        layout = QGridLayout()
        layout.addWidget(Label("Name: "), 0, 0)
        layout.addWidget(
            RichTextLabel(f"<span style='color: blue;'>{self.register.name}</span>"),
            0,
            1,
        )
        layout.addWidget(Label("Address: "), 1, 0)
        layout.addWidget(
            RichTextLabel(
                f"<span style='color: blue;'>0x{self.register.address:02X}</span>"
            ),
            1,
            1,
        )
        layout.addWidget(Label("Raw data: "), 2, 0)
        raw_data_label = RichTextLabel(
            f"<span style='color: blue;'>{self.register.data.bin}</span>"
        )
        layout.addWidget(raw_data_label, 2, 1)
        layout.addWidget(Label("Fields: "), 3, 0, 2, 1)

        fields_layout = QGridLayout()
        fields_layout.setColumnStretch(3, 10)
        for row, field_name in enumerate(self.register.get_field_names()):

            def mk_field_value_setter(fname: str, input_line_edit: LineEdit):
                def set_field_value():
                    min_val, max_val = self.register.get_field_definition(fname).range()
                    try:
                        actually_set_value = self.register.set_field_value(
                            fname,
                            max(min_val, min(max_val, float(input_line_edit.text()))),
                        )
                        input_line_edit.setText(f"{actually_set_value}")
                    except Exception:
                        current_field_value = self.register.get_field_value(fname)
                        input_line_edit.setText(f"{current_field_value}")
                    raw_data_label.setText(
                        f"<span style='color: blue;'>{self.register.data.bin}</span>"
                    )

                return set_field_value

            field_value_input_field = FieldValueInput(
                self,
                f"{self.register.get_field_value(field_name)}",
                self.register,
                field_name,
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
            field_definition = self.register.get_field_definition(field_name)
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
                Label("rw  " if field_definition.rw else "ro  "), row, 3
            )

            up_button = QToolButton()
            up_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            up_button.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
            )

            down_button = QToolButton()
            down_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            down_button.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
            )

            def mk_up(fvi: FieldValueInput) -> Callable[[], None]:
                return lambda: fvi.next_up()

            up_button.clicked.connect(mk_up(field_value_input_field))

            def mk_down(fvi: FieldValueInput) -> Callable[[], None]:
                return lambda: fvi.next_down()

            down_button.clicked.connect(mk_down(field_value_input_field))

            fields_layout.addWidget(
                HBoxPanel([field_value_input_field, up_button, down_button], margins=0),
                row,
                4,
            )

        fields_panel = Panel(fields_layout)
        fields_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        layout.addWidget(fields_panel, 5, 1)

        layout.setColumnStretch(1, 10)

        self.setStyleSheet("""
        QPushButton::focus { border: 2px solid #3b82f6; }
        QToolButton::hover { border: 2px solid #3b82f6; }
        """)
        self.setLayout(
            VBoxLayout(
                [
                    Panel(layout, background_color="white"),
                    W(stretch=1),
                    HorizonalLine(),
                    HBoxPanel(
                        [
                            W(stretch=1),
                            PushButton(
                                "Ok",
                                parent=self,
                                on_clicked=self.save_register,
                                auto_default=False,
                            ),
                            PushButton(
                                "Cancel",
                                parent=self,
                                on_clicked=self.close,
                                auto_default=False,
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

    def save_register(self):
        self.app.write_register_address_str.set_value(f"0x{self.register.address:02X}")
        self.app.write_register_value_str.set_value(f"0b{self.register.data.bin}")
        self.app.write_register()
        self.close()
