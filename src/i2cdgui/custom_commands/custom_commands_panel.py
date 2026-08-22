import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLabel, QMessageBox, QTextEdit
from pytide6 import HBoxPanel, Menu, PushButton, Splitter, VBoxPanel, W
from rgscore import RLinkI2C
from sprats.collections import Variable

from i2cdgui.app import App
from i2cdgui.custom_commands.custom_command_editor import CustomCommandsEditor
from i2cdgui.custom_commands.user_prompt import EvalExit, mk_prompt_user
from i2cdgui.gui_tools import (
    InTableSearchField,
    ListTableView,
    TableModelAllSelectableAndEnabled,
    TableModelWithFilterAction,
    TableModelWithOneColumn,
    apply_filter_to_text,
)
from i2cdgui.project import CustomCommand

# TODO: Switching project should refresh that that holds list of commands


@dataclass
class CommandLabelAndId:
    label: str
    id: str


class CommandsListModel(
    TableModelWithOneColumn,
    TableModelAllSelectableAndEnabled,
    TableModelWithFilterAction,
):
    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.commands_to_display: list[CommandLabelAndId] = self.mk_commands_to_display()

    def mk_commands_to_display(self) -> list[CommandLabelAndId]:
        return [CommandLabelAndId(c.label, c.label) for c in self.app.project.commands]

    def regenerate_commands_to_display(self):
        self.commands_to_display = self.mk_commands_to_display()

    def headerData(self, section, orientation, /, role=...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            match orientation:
                case Qt.Orientation.Horizontal:
                    return "Commands" if section == 0 else ""
                case Qt.Orientation.Vertical:
                    return None

        return super().headerData(section, orientation, role)

    def rowCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return len(self.commands_to_display)

    def data(self, index: QModelIndex | QPersistentModelIndex, /, role: int = ...) -> Any:
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            cmd = self.commands_to_display[index.row()]
            return cmd.label if index.column() == 0 else None
        else:
            return None

    def apply_filter(self, filter_text: str, post_filter_action: Callable[[], Any]):
        char_filter = list(filter_text)
        self.beginResetModel()
        try:
            self.commands_to_display.clear()
            commands_to_display_input = self.mk_commands_to_display()

            if char_filter == []:
                self.commands_to_display = commands_to_display_input
            else:
                for command in commands_to_display_input:
                    new_command_label = apply_filter_to_text(char_filter, command.label)
                    if new_command_label is not None:
                        self.commands_to_display.append(CommandLabelAndId(new_command_label, command.label))
        finally:
            self.endResetModel()
            post_filter_action()


class ResultsText(QTextEdit):
    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.setStyleSheet("QTextEdit { font-family: 'Monospace'; }")


class CustomCommandsPanel(VBoxPanel):
    def __init__(self, app: App):
        super().__init__(background_color="lightyellow", margins=(7, 7, 7, 0))
        self.app = app
        self.app.request_commands_reload = self.request_commands_reload

        self.commands_table = ListTableView(
            table_model=CommandsListModel(app),
            pass_key_press_event=self.pass_key_press_event,
            on_double_clicked=self.on_commands_table_double_clicked,
        )

        self.context_menu = Menu(
            parent=self,
            actions=[
                ("Run", self.eval_selected_command),
                ("Edit", self.edit_selected_command),
                ("Delete", self.delete_selected_command),
            ],
        )
        self.commands_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.commands_table.customContextMenuRequested.connect(
            lambda pos: self.context_menu.popup(self.commands_table.viewport().mapToGlobal(pos))
        )

        self.results_text = ResultsText(app)
        self.app.append_custom_commands_log_stdout = self.results_text.append

        self.search_field = InTableSearchField(
            table_view=self.commands_table,
            on_key_enter=lambda _: self.eval_selected_command(),
            close_action=lambda: None,
        )

        self.splitter = Splitter(
            Qt.Orientation.Horizontal,
            childrenCollapsible=False,
            handleWidth=8,
            widgets=[self.commands_table, self.results_text],
            margins=0,
        )

        self.withWidgets(
            HBoxPanel(
                widgets=[
                    PushButton("Define new command", on_clicked=self.define_new_command),
                    PushButton("Edit selected command", on_clicked=self.edit_selected_command),
                    PushButton("Delete selected command", on_clicked=self.delete_selected_command),
                    QLabel("        "),
                    PushButton("Run command", on_clicked=self.eval_selected_command),
                    W(stretch=1),
                ],
                margins=0,
            ),
            self.search_field,
            W(self.splitter, stretch=2),
        )

    def pass_key_press_event(self) -> Callable[[QKeyEvent], None]:
        def key_pressed(event: QKeyEvent) -> None:
            match event.key():
                case Qt.Key.Key_Return | Qt.Key.Key_Enter:
                    self.eval_selected_command()
                case Qt.Key.Key_Delete:
                    self.delete_selected_command()
                case _:
                    self.search_field.keyPressEvent(event)

        return key_pressed

    def eval_selected_command(self):
        selected_indexes = self.commands_table.selectedIndexes()
        if selected_indexes is None or len(selected_indexes) == 0:
            return
        try:
            selected_row = selected_indexes[0].row()

            command_label = self.commands_table.table_model.commands_to_display[selected_row].id
            for cmd in self.app.project.commands:
                if cmd.label == command_label:
                    link = RLinkI2C(self.app.i2c, self.app.device_address)

                    def mk_link_provider(lnk):
                        def provider():
                            return lnk

                        return provider

                    def print_into_commands_log_panel(*values: object):
                        self.app.append_custom_commands_log_stdout(" ".join([str(v) for v in values]))

                    def exit_eval():
                        raise EvalExit()

                    attrs = {}
                    for r in self.app.project.reg_list.registers:
                        attrs[r.name] = r.mk_embedding_class(mk_link_provider(link), auto_sync=False)()
                    dut_cls = type("DUT", (), attrs)
                    gg = {
                        "read": lambda r: r._read(),
                        "write": lambda r: r._write(),
                        "print": print_into_commands_log_panel,
                        "dut": dut_cls(),
                        "ctx": self.app.project.commands_context,
                        "prompt_user": mk_prompt_user(cmd.label),
                        "Variable": Variable,
                        "exit": exit_eval,
                    }
                    eval(cmd.compiled_code, gg)
                    return
        except EvalExit:
            pass
        except Exception as ex:
            tb_lines = traceback.format_exception(type(ex), ex, ex.__traceback__)
            x = "".join(tb_lines[2:])
            self.app.show_error(str(x))

    def on_commands_table_double_clicked(self, index: QModelIndex):
        self.eval_selected_command()

    def define_new_command(self):
        CustomCommandsEditor(self.app, cmd=None).exec()

    def get_selected_command(self) -> tuple[CustomCommand, int] | None:
        selected_indexes = self.commands_table.selectedIndexes()
        if selected_indexes is not None and len(selected_indexes) > 0:
            selected_row = selected_indexes[0].row()
            label = self.commands_table.table_model.commands_to_display[selected_row].id
            return self.app.project.get_custom_command_by_label(label), selected_row
        else:
            return None

    def delete_selected_command(self):
        match self.get_selected_command():
            case (cmd, row):
                ret = QMessageBox.question(
                    self.app.main_window,
                    "Delete custom command?",
                    "Please confirm that you want to delete this command?",
                    QMessageBox.StandardButton.Yes,
                    QMessageBox.StandardButton.No,
                )
                if ret == QMessageBox.StandardButton.Yes:
                    self.commands_table.table_model.beginResetModel()
                    self.app.project.delete_custom_command(cmd.label)
                    self.commands_table.table_model.regenerate_commands_to_display()
                    self.commands_table.table_model.endResetModel()
                    self.commands_table.selectRow(min(self.commands_table.table_model.rowCount() - 1, row))

    def edit_selected_command(self):
        match self.get_selected_command():
            case (cmd, _):
                CustomCommandsEditor(self.app, cmd).exec()

    def request_commands_reload(self):
        self.commands_table.table_model.beginResetModel()
        self.commands_table.table_model.regenerate_commands_to_display()
        self.commands_table.table_model.endResetModel()
