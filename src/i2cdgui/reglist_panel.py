from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

from bitstring import BitArray
from PySide6 import QtGui
from PySide6.QtCore import QItemSelection, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLabel, QMessageBox, QTextEdit
from pytide6 import HBoxPanel, Menu, PushButton, Splitter, VBoxPanel, W
from rgscore import Register, RegList

from i2cdgui.app import App
from i2cdgui.gui_tools import (
    InTableSearchField,
    ListTableView,
    TableModelAllSelectableAndEnabled,
    TableModelWithFilterAction,
    TableModelWithThreeColumns,
    apply_filter_to_text,
)
from i2cdgui.reg_def_editor import DefRegEditor, NewRegDefDialog, RegisterPrototype


@dataclass
class RowAndRegisterName:
    row: int
    name: str


@dataclass
class RegisterDisplayData:
    address: str
    name: str
    fields: str
    pure_name: str


def mk_registers_to_display(reg_list: RegList) -> list[RegisterDisplayData]:
    return [
        RegisterDisplayData(
            address=f"0x{register.address:02X}",
            name=register.name,
            fields=", ".join(register.get_field_names()),
            pure_name=register.name,
        )
        for register in reg_list.registers
    ]


class RegListModel(
    TableModelWithThreeColumns,
    TableModelAllSelectableAndEnabled,
    TableModelWithFilterAction,
):
    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.registers_to_display = mk_registers_to_display(self.app.project.reg_list)

    def regenerate_registers_to_display(self):
        self.registers_to_display = mk_registers_to_display(self.app.project.reg_list)

    def headerData(self, section, orientation, /, role=...) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            match section:
                case 0:
                    return "Address"
                case 1:
                    return "Register"
                case 2:
                    return "Fields"
                case _:
                    return ""
        elif (
            orientation == Qt.Orientation.Vertical
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return None
        else:
            return super().headerData(section, orientation, role)

    def rowCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return len(self.registers_to_display)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, /, role: int = ...
    ) -> Any:
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            register = self.registers_to_display[index.row()]
            match index.column():
                case 0:
                    return register.address
                case 1:
                    return register.name
                case 2:
                    return register.fields
                case _:
                    return None
        else:
            return None

    def apply_filter(self, filter_text: str, post_filter_action: Callable[[], Any]):
        char_filter = list(filter_text)
        self.beginResetModel()
        self.registers_to_display.clear()
        if char_filter == []:
            self.registers_to_display = mk_registers_to_display(
                self.app.project.reg_list
            )
            self.endResetModel()
            post_filter_action()
            return

        registers_to_display_input = mk_registers_to_display(self.app.project.reg_list)

        for register in registers_to_display_input:
            new_register_address = apply_filter_to_text(char_filter, register.address)
            new_register_name = apply_filter_to_text(char_filter, register.name)
            new_register_fields = apply_filter_to_text(char_filter, register.fields)

            fields_ = [new_register_address, new_register_name, new_register_fields]
            if len([a for a in fields_ if a is not None]) > 0:
                # we have something to display
                if new_register_address is None:
                    new_register_address = register.address

                if new_register_name is None:
                    new_register_name = register.name

                if new_register_fields is None:
                    new_register_fields = register.fields

                # add to display
                self.registers_to_display.append(
                    RegisterDisplayData(
                        address=new_register_address,
                        name=new_register_name,
                        fields=new_register_fields,
                        pure_name=register.name,
                    )
                )
        self.endResetModel()
        post_filter_action()


class RegisterInfoPanel(VBoxPanel):
    pass


class RegInfoText(QTextEdit):
    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.setStyleSheet("QTextEdit { font-family: 'Monospace'; }")
        self.register: Register | None = None
        self.__lock = Lock()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_A and event.modifiers() == (
            Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier
        ):
            super().keyPressEvent(event)

    def reload_register(self):
        if self.register is not None:
            self.show_register(self.register)

    def show_register(self, register: Register) -> None:
        with self.__lock:
            self.register = register
            fields_rows = ""
            raw_result = self.app.project.get_raw_result_for_address(register.address)
            if raw_result is not None:
                register.data.clear()
                register.data.append(BitArray(f"0b{raw_result.value_bin}"))

            for field_name in register.get_field_names():
                field_def = register.get_field_definition(field_name)
                fields_rows += (
                    f"<tr><td>&nbsp;</td><td><p style='color: blue;'>{field_def.name}&nbsp;&nbsp;</p></td>"
                    f"<td>[{field_def.end_offset()}:{field_def.offset}]&nbsp;&nbsp;</td>"
                    f"<td>{field_def.signed}{field_def.width}.{field_def.fractional}</td>"
                )
                if field_def.rw:
                    fields_rows += "<td>&nbsp;&nbsp;r/w</td>"
                else:
                    fields_rows += "<td>&nbsp;&nbsp;r/o</td>"
                if raw_result is None:
                    fields_rows += "<td></td></tr>"
                else:
                    fields_rows += f"<td>&nbsp;&nbsp;=> {register.get_field_value(field_def.name)}</td></tr>"

            self.setText(
                f"""
                <table>
                <tbody>
                <tr><td>Register:</td><td colspan=5><p style='color: blue;'>{register.name}</p></td></tr>
                <tr><td>Address:</td><td colspan=5><p style='color: blue;'>0x{register.address:02X}</p></td></tr>
                <tr><td>Width (bits):&nbsp;&nbsp;</td><td colspan=5><p style='color: blue;'>{register.width}</p></td></tr>
                <tr><td colspan=6>Fields:</td></tr>
                {fields_rows}
                </tbody>
                </table>
            """.strip()
            )


class RegListTableView(ListTableView):
    def __init__(
        self,
        table_model: RegListModel,
        pass_key_press_event: Callable[[], Callable[[QKeyEvent], None]],
        on_double_clicked: Callable[[QModelIndex], None] | None,
    ):
        super().__init__(table_model, pass_key_press_event, on_double_clicked)


class RegListPanel(VBoxPanel):
    def __init__(self, app: App):
        super().__init__(background_color="lightyellow", margins=(7, 7, 7, 0))
        self.app = app
        self.reglist_table = ListTableView(
            table_model=RegListModel(app),
            pass_key_press_event=self.pass_key_press_event,
            on_double_clicked=self.on_actions_table_double_clicked,
        )
        app.request_reglist_reload = self.request_reglist_reload

        self.context_menu = Menu(
            parent=self,
            actions=[
                ("Read register", self.read_selected_register),
                ("Write register", self.write_selected_register),
                Menu.Separator,
                ("Edit register", self.edit_selected_register),
                ("Define new register", lambda: NewRegDefDialog(self.app).exec()),
                ("Delete register", self.delete_selected_register),
            ],
        )
        self.reglist_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.reglist_table.customContextMenuRequested.connect(
            lambda pos: self.context_menu.popup(
                self.reglist_table.viewport().mapToGlobal(pos)
            )
        )

        self.search_field = InTableSearchField(
            table_view=self.reglist_table,
            on_key_enter=lambda _: self.read_selected_register(),
            close_action=lambda: None,
        )

        def select_register(register: Register) -> None:
            try:
                for row, rdd in enumerate(
                    self.reglist_table.table_model.registers_to_display
                ):
                    if rdd.pure_name == register.name:
                        self.reglist_table.selectRow(row)
                        return
            finally:
                self.search_field.setFocus()

        app.request_reglist_select_register = select_register

        self.register_text = RegInfoText(app)

        def selection_changed(selected_item: QItemSelection, _):
            selected_indexes = selected_item.indexes()
            if selected_indexes is not None and len(selected_indexes) > 0:
                register_name = self.reglist_table.table_model.registers_to_display[
                    selected_indexes[0].row()
                ].pure_name
                self.register_text.show_register(
                    app.project.reg_list.get_register_by_name(register_name)
                )

        self.reglist_table.selectionModel().selectionChanged.connect(selection_changed)

        self.splitter = Splitter(
            Qt.Orientation.Horizontal,
            childrenCollapsible=False,
            handleWidth=8,
            widgets=[self.reglist_table, self.register_text],
            margins=0,
        )
        self.withWidgets(
            HBoxPanel(
                widgets=[
                    PushButton(
                        "Define new register",
                        on_clicked=lambda: NewRegDefDialog(self.app).exec(),
                    ),
                    PushButton("Edit register", on_clicked=self.edit_selected_register),
                    PushButton(
                        "Delete register", on_clicked=self.delete_selected_register
                    ),
                    QLabel("        "),
                    PushButton("Read register", on_clicked=self.read_selected_register),
                    PushButton(
                        "Write register", on_clicked=self.write_selected_register
                    ),
                    W(stretch=1),
                ],
                margins=0,
            ),
            self.search_field,
            W(self.splitter, stretch=2),
        )

        self.app.registers_values_changed = self.registers_values_changed

    def registers_values_changed(self, address: int):
        if (
            self.register_text.register is not None
            and self.register_text.register.address == address
        ):
            self.register_text.reload_register()

    def request_reglist_reload(self):
        self.reglist_table.table_model.beginResetModel()
        self.reglist_table.table_model.regenerate_registers_to_display()
        self.register_text.clear()
        self.reglist_table.table_model.endResetModel()

    def pass_key_press_event(self) -> Callable[[QKeyEvent], None]:
        def key_pressed(event: QKeyEvent) -> None:
            if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                self.read_selected_register()
            else:
                self.search_field.keyPressEvent(event)

        return key_pressed

    def on_actions_table_double_clicked(self, index: QModelIndex):
        self.read_selected_register()

    def define_new_register(self):
        NewRegDefDialog(self.app).exec()

    def get_selected_register_name(self) -> RowAndRegisterName | None:
        selected_indexes = self.reglist_table.selectedIndexes()
        if selected_indexes is not None and len(selected_indexes) > 0:
            selected_row = selected_indexes[0].row()
            return RowAndRegisterName(
                row=selected_row,
                name=self.reglist_table.table_model.registers_to_display[
                    selected_row
                ].pure_name,
            )
        else:
            return None

    def edit_selected_register(self):
        row_and_name = self.get_selected_register_name()
        if row_and_name is not None:
            register = self.app.project.reg_list.get_register_by_name(row_and_name.name)
            DefRegEditor(
                app=self.app,
                windowTitle="Edit Register",
                is_new_register=False,
                register_proto=RegisterPrototype.from_register(
                    self.app.project.reg_list.get_register_by_name(register.name)
                ),
            ).exec()

    def delete_selected_register(self):
        register = self.get_selected_register_name()
        if register is not None:
            ret = QMessageBox.question(
                self.app.main_window,
                "Delete register?",
                f"Please confirm that you want to delete register [{register.name}]?",
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.Yes:
                self.app.project.reg_list.delete_register_by_name(register.name)
                self.app.request_reglist_reload()
                self.search_field.textChanged.emit(self.search_field.text())
                self.reglist_table.selectRow(register.row)
                self.app.update_results_display_data()
                self.app.request_results_reload()

    def read_selected_register(self):
        register = self.get_selected_register_name()
        if register is not None:
            r = self.app.project.reg_list.get_register_by_name(register.name)
            self.app.change_read_register_address(f"0x{r.address:02X}")
            self.app.read_register()

    def write_selected_register(self):
        """TODO: Implement me"""
