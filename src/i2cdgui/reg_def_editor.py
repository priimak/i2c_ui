import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import reduce

from PySide6 import QtGui
from PySide6.QtCore import Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QFrame, QLayoutItem
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
from sprats.collections import Variable

from i2cdgui.app import App


class FractionalInput(LineEdit):
    def __init__(self, value: str, on_text_change: Callable[[str], None] | None = None):
        super().__init__(
            text=value,
            with_fixed_width_for_text="00",
            validator=QRegularExpressionValidator("^[0-9]{0,2}$"),
            on_text_change=on_text_change,
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def reformat_input_text(self):
        if self.text() == "":
            self.setText("0")

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.reformat_input_text()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Return:
            self.reformat_input_text()

        super().keyPressEvent(event)


class FieldNameInput(LineEdit):
    def __init__(self, value: str, on_text_change: Callable[[str], None] | None = None):
        super().__init__(
            text=value,
            with_fixed_width_for_text="Very Long Field Name",
            validator=QRegularExpressionValidator("^[a-zA-Z_]?[a-zA-Z0-9_]*$"),
            on_text_change=on_text_change,
        )


@dataclass
class FieldDevGUIElements:
    field_name_input_field: FieldNameInput
    checkboxes: list[CheckBox]
    width_label: Label
    rw_selector: ComboBox
    signed_selector: ComboBox
    fractional_input_field: FractionalInput


@dataclass
class RegisterPrototype:
    name: str
    address: int | None
    width: int
    model: list[FieldDef]
    gui_model: list[FieldDevGUIElements]

    __address_str: str = ""

    def __post_init__(self):
        self.__address_str = "" if self.address is None else f"0x{self.address:02X}"

    def set_name(self, name: str):
        self.name = name

    def set_address(self, address: str) -> None:
        self.__address_str = address
        self.address = 0 if address in ["", "0x"] else int(address, 16)

    def to_register(self) -> Register:
        if self.name is None or self.name.strip() == "":
            raise ValueError("Register must have a name")
        elif not Register.register_name_re.match(self.name):
            raise ValueError(
                "Register name must not be empty and contain only numbers, letters and (_) underscores."
            )
        elif self.__address_str in ["", "0x"]:
            raise ValueError("Register must have an address")
        elif self.model == []:
            raise ValueError("Register must have at least one field")
        elif len([fd for fd in self.model if fd.width == 0]) > 0:
            raise ValueError(
                "Every field must have bits that it is picking from the register"
            )
        elif len([fd for fd in self.model if fd.name.strip() == ""]) > 0:
            raise ValueError("Every field must have a name")
        else:
            return Register(
                bit_len=self.width,
                address=self.address,
                name=self.name,
                link=None,
                model=self.model,
            )

    @staticmethod
    def from_register(register: Register) -> "RegisterPrototype":
        return RegisterPrototype(
            name="" if register.name is None else register.name,
            address=register.address,
            width=register.width,
            model=[fd.copy() for fd in register._model],
            gui_model=[],
        )

    # @staticmethod
    # def from_results_data(app: App, register_address: int, num_bits: int):
    #     return DefRegEditor(
    #         app,
    #         windowTitle="Create new register",
    #         is_new_register=True,
    #         register_proto=RegisterPrototype(
    #             name="",
    #             address=register_address,
    #             width=num_bits,
    #             model=[
    #                 FieldDef(
    #                     name="",
    #                     offset=0,
    #                     signed="U",
    #                     width=0,
    #                     fractional=0,
    #                     rw=True,
    #                 )
    #             ],
    #             gui_model=[],
    #         ),
    #     )


class AddressInput(LineEdit):
    valid_address_re = re.compile("^(0x)?[0-9a-fA-F]+$")

    def __init__(self, register: RegisterPrototype):
        super().__init__(
            text="" if register.address is None else f"0x{register.address:02X}",
            with_fixed_width_for_text="0xFF",
            validator=QRegularExpressionValidator("^(0x)?[0-9a-fA-F]{0,4}$"),
            on_text_change=register.set_address,
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def reformat_input_text(self):
        entered_address = self.text().strip()
        if re.match("^(0x)?[0-9a-fA-F]{1,4}$", entered_address):
            address = int(self.text(), 16)
            self.setText(f"0x{address:02X}")

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.reformat_input_text()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Return:
            self.reformat_input_text()

        super().keyPressEvent(event)


class DefRegEditor(Dialog):
    def __init__(
        self,
        app: App,
        *,
        is_new_register: bool,
        register_proto: RegisterPrototype,
        windowTitle: str | None = None,
    ):
        super().__init__(app.main_window, windowTitle=windowTitle, modal=True)
        self.app = app
        self.is_new_register = is_new_register
        self.cb_toggle_enabled = True
        self.register_proto = register_proto
        self.original_register_name = self.register_proto.name
        name = "" if self.register_proto.name is None else self.register_proto.name
        self.register_proto.width = 8 * (self.register_proto.width // 8) + (
            8 if (self.register_proto.width % 8) > 0 else 0
        )
        self.new_register_address = ""

        self.fields_panel = self.build_fields_panel(VBoxPanel(margins=0))

        def mk_line():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            return line

        def add_new_field():
            self.remove_all_fields_gui_elements()
            self.register_proto.model.append(
                FieldDef(name="", offset=0, signed="U", width=0, fractional=0, rw=True)
            )
            self.register_proto.gui_model.clear()
            self.build_fields_panel(self.fields_panel)

        self.setLayout(
            VBoxLayout(
                [
                    HBoxPanel(
                        [
                            Label("Name"),
                            LineEdit(
                                name,
                                on_text_change=self.register_proto.set_name,
                                with_fixed_width_for_text="Very Long Register Name",
                            ),
                            Label("  Addr"),
                            AddressInput(self.register_proto),
                            Label(
                                f"  This register is {self.register_proto.width} bits wide"
                            ),
                            W(stretch=1),
                        ],
                        margins=0,
                    ),
                    mk_line(),
                    HBoxPanel(
                        [
                            Label("Fields"),
                            PushButton(
                                "Add New Field",
                                on_clicked=add_new_field,
                                auto_default=False,
                            ),
                            W(stretch=1),
                        ],
                        margins=0,
                    ),
                    self.fields_panel,
                    W(stretch=1),
                    mk_line(),
                    HBoxPanel(
                        [
                            W(stretch=1),
                            PushButton(
                                "Ok", on_clicked=self.save_register, auto_default=False
                            ),
                            PushButton(
                                "Cancel", on_clicked=self.close, auto_default=False
                            ),
                        ],
                        margins=0,
                    ),
                ]
            )
        )

    def remove_all_fields_gui_elements(self):
        fields_panel_layout = self.fields_panel.layout()
        for _ in range(fields_panel_layout.count()):
            w: QLayoutItem = fields_panel_layout.takeAt(0)
            w.widget().setParent(None)
            fields_panel_layout.removeItem(w)

        fields_panel_layout.update()

    def save_register(self):
        try:
            new_register = self.register_proto.to_register()
            if self.is_new_register:
                self.app.project.reg_list.add(new_register)
            else:
                # we are editing register
                original_register = self.app.project.reg_list.get_register_by_name(
                    self.original_register_name
                )
                self.app.project.reg_list.update_register_def(
                    original_register, new_register
                )

            self.app.request_reglist_reload()
            self.app.request_reglist_select_register(new_register)
            self.app.update_results_display_data()
            self.app.request_results_reload()
            self.close()
        except Exception as ex:
            self.app.show_error(f"{ex}")

    def build_fields_panel(self, fields_panel: VBoxPanel) -> VBoxPanel:
        wgs = []

        def other_used_bits(but_fd: FieldDef) -> set[int]:
            other_fields = [fd for fd in self.register_proto.model if fd is not but_fd]
            used_register_bits = [
                set(range(fd.offset, fd.offset + fd.width)) for fd in other_fields
            ]
            return reduce(lambda acc, v: acc | v, used_register_bits, set())

        def mk_bare_cb(field_idx: int, offset: int) -> CheckBox:
            cb = CheckBox()
            cb.setStyleSheet("QCheckBox:disabled {background-color: black;}")
            cb.setProperty("field_idx", field_idx)
            cb.setProperty("offset", offset)
            return cb

        for field_idx, field_def in enumerate(self.register_proto.model):

            def mk_rw_setter(fd: FieldDef):
                def set_rw(value: str):
                    fd.rw = value == "rw"

                return set_rw

            def mk_signed_setter(fd: FieldDef):
                def set_signed(value: str):
                    fd.signed = "S" if value == "Signed" else "U"

                return set_signed

            def mk_fractional_setter(fd: FieldDef):
                def set_fractional(value: str):
                    if value == "":
                        fd.fractional = 0
                    else:
                        fd.fractional = int(value)

                return set_fractional

            def mk_field_name_setter(fd: FieldDef):
                def set_name(value: str):
                    fd.name = value

                return set_name

            self.register_proto.gui_model.append(
                FieldDevGUIElements(
                    field_name_input_field=FieldNameInput(
                        field_def.name, on_text_change=mk_field_name_setter(field_def)
                    ),
                    checkboxes=[
                        mk_bare_cb(field_idx, offset)
                        for offset in range(self.register_proto.width)
                    ],
                    width_label=Label(f"{field_def.width}."),
                    rw_selector=ComboBox(
                        items=["rw", "ro"],
                        current_selection="rw" if field_def.rw else "ro",
                        on_text_change=mk_rw_setter(field_def),
                    ),
                    signed_selector=ComboBox(
                        items=["Unsinged", "Signed"],
                        current_selection=(0 if field_def.signed == "U" else 1),
                        on_text_change=mk_signed_setter(field_def),
                    ),
                    fractional_input_field=FractionalInput(
                        f"{field_def.fractional}",
                        on_text_change=mk_fractional_setter(field_def),
                    ),
                )
            )
        for field_idx, field_def in enumerate(self.register_proto.model):
            bits_to_disable: set[int] = other_used_bits(field_def)
            # field_width_label = Label(f"{field_def.width}.")

            def mk_cb(i: int, bits_to_disable: set[int], field_def: FieldDef):
                cb: CheckBox = self.register_proto.gui_model[field_idx].checkboxes[i]
                cb.setChecked(field_def.offset <= i <= field_def.end_offset())
                cb.setEnabled(i not in bits_to_disable)

                def mk_cb_toggled(cbb: CheckBox):
                    def cb_toggled(on: bool):
                        if not self.cb_toggle_enabled:
                            return

                        field_idx: int = cbb.property("field_idx")
                        offset: int = cbb.property("offset")
                        field_def: FieldDef = self.register_proto.model[field_idx]
                        if offset == (field_def.end_offset() + 1):
                            field_def.width += 1
                        elif offset == field_def.offset - 1:
                            field_def.offset -= 1
                            field_def.width += 1
                        elif field_def.offset < offset <= field_def.end_offset():
                            field_def.width = offset - field_def.offset
                        elif field_def.offset == offset:
                            field_def.offset += 1
                            field_def.width -= 1
                        else:
                            field_def.offset = offset
                            field_def.width = 1 if on else 0

                        # update numerical type width label
                        self.register_proto.gui_model[field_idx].width_label.setText(
                            f"{field_def.width}."
                        )

                        # now update gui checkboxes
                        ids_checked = set(
                            range(field_def.offset, field_def.end_offset() + 1)
                        )
                        try:
                            self.cb_toggle_enabled = False
                            for cb in self.register_proto.gui_model[
                                field_idx
                            ].checkboxes:
                                idx: int = cb.property("offset")
                                cb.setChecked(idx in ids_checked)
                        finally:
                            self.cb_toggle_enabled = True

                        # now update other fields disabling checkboxes
                        for j, other_field_def in enumerate(self.register_proto.model):
                            if j != field_idx:
                                bits_to_disable: set[int] = other_used_bits(
                                    other_field_def
                                )
                                for cb in self.register_proto.gui_model[j].checkboxes:
                                    cb.setEnabled(
                                        cb.property("offset") not in bits_to_disable
                                    )

                    return cb_toggled

                cb.toggled.connect(mk_cb_toggled(cb))

                return cb

            cbs = [
                mk_cb(i, bits_to_disable, field_def)
                for i in range(self.register_proto.width)[::-1]
            ]

            def mk_delete_action(idx: int) -> Callable[[], None]:
                def delete_action():
                    self.remove_all_fields_gui_elements()
                    del self.register_proto.model[idx]
                    self.register_proto.gui_model.clear()
                    self.build_fields_panel(fields_panel)

                return delete_action

            wgs.append(
                HBoxPanel(
                    cbs
                    + [
                        Label(" "),
                        self.register_proto.gui_model[field_idx].field_name_input_field,
                        self.register_proto.gui_model[field_idx].rw_selector,
                        self.register_proto.gui_model[field_idx].signed_selector,
                        self.register_proto.gui_model[field_idx].width_label,
                        self.register_proto.gui_model[field_idx].fractional_input_field,
                        Label("  "),
                        W(stretch=1),
                        PushButton(
                            "Delete",
                            on_clicked=mk_delete_action(field_idx),
                            auto_default=False,
                        ),
                    ],
                    margins=0,
                )
            )
        fields_panel.layout().addWidgets(wgs)
        return fields_panel


class NewRegDefDialog(Dialog):
    def __init__(self, app: App):
        super().__init__(app.main_window, windowTitle="Create new register", modal=True)
        self.app = app
        self.bit_width: Variable[int] = Variable(8, valid_values=[8, 16, 24, 32])

        def open_edit_dialog():
            self.close()
            DefRegEditor(
                app,
                windowTitle="Create new register",
                is_new_register=True,
                register_proto=RegisterPrototype(
                    name="",
                    address=None,
                    width=self.bit_width.value,
                    model=[
                        FieldDef(
                            name="",
                            offset=0,
                            signed="U",
                            width=0,
                            fractional=0,
                            rw=True,
                        )
                    ],
                    gui_model=[],
                ),
            ).exec()

        self.setLayout(
            VBoxLayout(
                [
                    HBoxPanel(
                        [
                            Label(
                                "How wide (in number of bits) do you want this register to be?"
                            ),
                            ComboBox(reactive_variable=self.bit_width),
                        ]
                    ),
                    HBoxPanel(
                        [
                            W(stretch=1),
                            PushButton(
                                "Ok", on_clicked=open_edit_dialog, auto_default=True
                            ),
                            PushButton(
                                "Cancel", on_clicked=self.close, auto_default=False
                            ),
                        ]
                    ),
                ]
            )
        )


def open_create_or_edit_register_from_template(
    app: App, register_address: int, width_bits: int
):
    register = app.project.reg_list.get_register_by_address(register_address)
    if register is None:
        return DefRegEditor(
            app,
            windowTitle="Create new register",
            is_new_register=True,
            register_proto=RegisterPrototype(
                name="",
                address=register_address,
                width=width_bits,
                model=[
                    FieldDef(
                        name="",
                        offset=0,
                        signed="U",
                        width=0,
                        fractional=0,
                        rw=True,
                    )
                ],
                gui_model=[],
            ),
        ).exec()
    else:
        DefRegEditor(
            app=app,
            windowTitle="Edit Register",
            is_new_register=False,
            register_proto=RegisterPrototype.from_register(register),
        ).exec()
