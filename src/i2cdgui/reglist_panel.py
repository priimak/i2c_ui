from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLabel
from pytide6 import HBoxPanel, PushButton, VBoxPanel, W
from rgscore import RegList

from i2cdgui.app import App
from i2cdgui.gui_tools import (
    InTableSearchField,
    ListTableView,
    TableModelAllSelectableAndEnabled,
    TableModelWithFilterAction,
    TableModelWithTwoColumns,
    apply_filter_to_text,
)


@dataclass
class RegisterDisplayData:
    address: str
    name: str


def mk_registers_to_display(reg_list: RegList) -> list[RegisterDisplayData]:
    return [
        RegisterDisplayData(address=f"0x{register.address:04X}", name=register.name)
        for register in reg_list.registers
    ]


class RegListModel(
    TableModelWithTwoColumns,
    TableModelAllSelectableAndEnabled,
    TableModelWithFilterAction,
):
    def __init__(self, app: App):
        super().__init__()
        self.app = app
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
                case _:
                    return None
        else:
            return None

    def apply_filter(self, filter_text: str, post_filter_action: Callable[[], Any]):
        char_filter = list(filter_text)
        self.beginResetModel()
        self.registers_to_display.clear()
        if char_filter == []:
            self.registers_to_display = mk_registers_to_display(self.app.project.reg_list)
            self.endResetModel()
            post_filter_action()
            return

        registers_to_display_input = mk_registers_to_display(self.app.project.reg_list)

        for register in registers_to_display_input:
            new_register_address = apply_filter_to_text(char_filter, register.address)
            new_register_name = apply_filter_to_text(char_filter, register.name)

            if new_register_address is None and new_register_name is not None:
                new_register_address = register.address

            if new_register_address is not None and new_register_name is None:
                new_register_name = register.name

            if new_register_address is not None and new_register_name is not None:
                # add to display
                self.registers_to_display.append(
                    RegisterDisplayData(
                        address=new_register_address, name=new_register_name
                    )
                )
        self.endResetModel()
        post_filter_action()



class RegListPanel(VBoxPanel):
    def __init__(self, app: App):
        super().__init__(background_color="lightyellow", margins=(7, 7, 7, 0))

        self.reglist_table = ListTableView(
            table_mode=RegListModel(app),
            pass_key_press_event=self.pass_key_press_event,
            on_double_clicked=self.on_actions_table_double_clicked,
        )
        self.search_field = InTableSearchField(
            table_view=self.reglist_table,
            on_key_enter=lambda index: None,
            close_action=lambda: None,
        )

        self.withWidgets(
            [
                HBoxPanel(
                    widgets=[
                        PushButton("Define new register"),
                        PushButton("Edit register"),
                        PushButton("Delete register"),
                        QLabel("        "),
                        PushButton("Read register"),
                        W(stretch=1)
                    ],
                    margins=0,
                ),
                self.search_field,
                HBoxPanel([self.reglist_table], margins=0),
            ]
        )

    def pass_key_press_event(self) -> Callable[[QKeyEvent], None]:
        return self.search_field.keyPressEvent

    def on_actions_table_double_clicked(self, index: QModelIndex):
        pass
