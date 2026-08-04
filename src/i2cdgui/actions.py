from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6 import QtCore
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSize,
    Qt,
)
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import QAbstractItemView, QLineEdit, QTableView
from pytide6 import Dialog, Label, VBoxLayout
from pytide6.inputs import LineEdit

from i2cdgui.app import App
from i2cdgui.gui_tools import Txt2HTMLDelegate
from i2cdgui.projects_gui import (
    DeleteProjectDialog,
    NewProjectDialog,
    OpenProjectDialog,
    SaveAsProjectDialog,
)
from i2cdgui.reg_def_editor import DefRegEditor


@dataclass(slots=True, frozen=True)
class Action:
    name: str
    action: Callable[[App], Any]


ACTIONS = [
    Action("Add new variable to watch list", None),
    Action("Create new project", lambda app: NewProjectDialog(app).exec()),
    Action(
        "Define new register",
        lambda app: DefRegEditor(app, windowTitle="New Register").exec(),
    ),
    Action(
        "Delete currently active project",
        lambda app: DeleteProjectDialog(app, app.project.name).exec(),
    ),
    Action("Exit/Quit application", lambda app: app.exit_application[0]()),
    Action("Export project into file", None),
    Action("Import project from file", None),
    Action("Open project", lambda app: OpenProjectDialog(app).exec()),
    Action("Open regList editor", None),
    Action("Read register", None),
    Action(
        "Save currently open project under a different name",
        lambda app: SaveAsProjectDialog(app).exec(),
    ),
    Action("Write register", None),
]


class ActionsModel(QAbstractTableModel):
    def __init__(self, tv: QTableView, app: App):
        super().__init__()
        self.app = app
        self.tv = tv
        self.actions_to_display = ACTIONS.copy()

    def headerData(self, section, orientation, /, role=...) -> Any:
        return None

    def rowCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return len(self.actions_to_display)

    def columnCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return 1

    def data(
        self, index: QModelIndex | QPersistentModelIndex, /, role: int = ...
    ) -> Any:
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return self.actions_to_display[index.row()].name
        else:
            return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def apply_filter(self, char_filter: list[str]):
        self.beginResetModel()
        self.actions_to_display.clear()
        if char_filter == []:
            self.actions_to_display = ACTIONS.copy()
            self.endResetModel()
            self.tv.selectRow(0)
            return

        for action in ACTIONS:
            j = 0
            new_label = ""
            for i in range(len(action.name)):
                if (
                    j < len(char_filter)
                    and char_filter[j].lower() == action.name[i].lower()
                ):
                    j += 1
                    new_label += f'<span style="background-color: pink; color: #000000;">{action.name[i]}</span>'
                else:
                    new_label += action.name[i]
            if j == len(char_filter):
                self.actions_to_display.append(Action(new_label, action.action))

        self.endResetModel()
        self.tv.selectRow(0)


class ActionsTableView(QTableView):
    def __init__(
        self,
        parent: Dialog,
        app: App,
        pass_key_press_event: Callable[[], Callable[[QKeyEvent], None]],
    ):
        super().__init__(None)
        self.parent: Dialog = parent
        self.pass_key_press_event = pass_key_press_event
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().hide()
        self.select_chars = []
        self.actions_model = ActionsModel(self, app)
        self.setModel(self.actions_model)
        self.setItemDelegate(Txt2HTMLDelegate())

        def do_action(index: QModelIndex):
            parent.close()
            self.actions_model.actions_to_display[index.row()].action(app)

        self.doubleClicked.connect(do_action)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self.pass_key_press_event()(event)


class SearchField(LineEdit):
    def __init__(
        self,
        parent: Dialog,
        /,
        app: App,
        on_text_change: Callable[[str], None],
        actions_table: ActionsTableView,
    ):
        super().__init__(on_text_change=on_text_change)
        self.parent = parent
        self.app = app
        self.actions_table = actions_table

        # place "find" icon on the left side of search text field.
        self.addAction(
            QIcon.fromTheme(QIcon.ThemeIcon.EditFind),
            QLineEdit.ActionPosition.LeadingPosition,
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        event_key = event.key()
        match event_key:
            case Qt.Key.Key_Escape:
                if self.text() == "":
                    self.parent.close()
                else:
                    self.setText("")
                    return

            case Qt.Key.Key_Return:
                selected_rows = self.actions_table.selectedIndexes()
                if selected_rows == []:
                    self.parent.close()
                else:
                    self.parent.close()
                    self.actions_table.actions_model.actions_to_display[
                        selected_rows[0].row()
                    ].action(self.app)
                return

            case Qt.Key.Key_Down:
                selected_rows = self.actions_table.selectedIndexes()
                if selected_rows == []:
                    self.actions_table.selectRow(0)
                else:
                    next_row = selected_rows[0].row() + 1
                    if next_row <= self.actions_table.actions_model.rowCount():
                        self.actions_table.selectRow(next_row)
                return

            case Qt.Key.Key_Up:
                selected_rows = self.actions_table.selectedIndexes()
                if selected_rows == []:
                    self.actions_table.selectRow(0)
                else:
                    next_row = selected_rows[0].row() - 1
                    if next_row >= 0:
                        self.actions_table.selectRow(next_row)
                return

        super().keyPressEvent(event)


class FindActionDialog(Dialog):
    def __init__(self, app: App):
        super().__init__(app.main_window, windowTitle="Find Action", modal=True)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Window
        )
        self.app = app
        actions_table = ActionsTableView(
            self, app, pass_key_press_event=self.pass_key_press_event
        )
        self.search_field = SearchField(
            self,
            app=app,
            on_text_change=lambda x: actions_table.actions_model.apply_filter(list(x)),
            actions_table=actions_table,
        )
        self.setLayout(
            VBoxLayout([Label("Find Action"), self.search_field, actions_table])
        )
        self.search_field.setFocus()
        screen_dim: QSize = app.q_application.primaryScreen().size()
        self.resize(int(screen_dim.width() / 2), int(screen_dim.height() / 3))

    def pass_key_press_event(self) -> Callable[[QKeyEvent], None]:
        return self.search_field.keyPressEvent
