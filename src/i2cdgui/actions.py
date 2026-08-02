from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSize,
    Qt,
)
from PySide6.QtWidgets import QAbstractItemView, QTableView
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


@dataclass(slots=True, frozen=True)
class Action:
    name: str
    action: Callable[[App], Any]

ACTIONS = [
    Action("Create new project", lambda app: NewProjectDialog(app).exec()),
    Action("Delete currently opened project", lambda app: DeleteProjectDialog(app, app.project.name).exec()),
    Action("Exit/Quit application", lambda app: app.exit_application[0]()),
    Action("Open project", lambda app: OpenProjectDialog(app).exec()),
    Action("Read register", None),
    Action("Save currently open project under a different name", lambda app: SaveAsProjectDialog(app).exec()),
    Action("Write register", None),
    Action("Define new register", None),
    Action("Open regList editor", None),
    Action("Add new variable to watch list", None),
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

    def data(self, index: QModelIndex | QPersistentModelIndex, /, role: int = ...) -> Any:
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return self.actions_to_display[index.row()].name
        else:
            return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def apply_filter(self, char_filter: list[str]):
        self.beginResetModel()
        self.actions_to_display.clear()
        # self.project_names_raw.clear()
        if char_filter == []:
            self.actions_to_display = ACTIONS.copy()
            # self.project_names_raw = self.project_names_to_display.copy()
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
                    new_label += f'<span style="background-color: #0000ff; color: #ffffff;">{action.name[i]}</span>'
                else:
                    new_label += action.name[i]
            if j == len(char_filter):
                self.actions_to_display.append(Action(new_label, action.action))
                # self.project_names_raw.append(project_name)

        self.endResetModel()
        self.tv.selectRow(0)



class ActionsTableView(QTableView):
    def __init__(self, app: App, selection_filter_changed: Callable[[list[str]], None]):
        super().__init__(None)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().hide()
        self.select_chars = []
        self.actions_model = ActionsModel(self, app)
        self.setModel(self.actions_model)
        self.setItemDelegate(Txt2HTMLDelegate())
        self.selection_filter_changed = selection_filter_changed


class FindActionDialog(Dialog):
    def __init__(self, app: App):
        super().__init__(app.main_window, windowTitle="Find Action", modal=True)
        self.app = app
        actions_table = ActionsTableView(app, None)
        search_field = LineEdit(on_text_change=lambda x: actions_table.actions_model.apply_filter(list(x)))
        self.setLayout(VBoxLayout([
            Label("Find Action"),
            search_field,
            actions_table
        ]))
        search_field.setFocus()
        screen_dim: QSize = app.q_application.primaryScreen().size()
        screen_width, screen_height = screen_dim.width(), screen_dim.height()
        self.resize(int(screen_width/2), int(screen_height/3))


