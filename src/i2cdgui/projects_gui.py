from collections.abc import Callable
from typing import Any, override

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTableView,
    QTableWidget,
)
from pytide6 import Dialog, HBoxPanel, Label, PushButton, RichTextLabel, VBoxLayout, W
from pytide6.inputs import LineEdit
from sprats.collections import Variable

from i2cdgui.app import App
from i2cdgui.gui_tools import Txt2HTMLDelegate
from i2cdgui.project import PROJECT_VALID_CHAR_RE


class ProjectDialog(Dialog):
    def __init__(self, parent, title: str) -> None:
        super().__init__(parent, windowTitle=title, modal=True)
        self.layout = VBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(Label(title))
        self.projects = QTableWidget(self)


class ProjectsModel(QAbstractTableModel):
    def __init__(self, tv: QTableView, app: App):
        super().__init__()
        self.app = app
        self.project_names = app.projects.list_projects()
        self.project_names.sort()
        self.project_names_to_display = self.project_names.copy()
        self.project_names_raw = self.project_names_to_display.copy()
        self.tv = tv

    def apply_filter(self, char_filter: list[str]):
        self.beginResetModel()
        self.project_names_to_display.clear()
        self.project_names_raw.clear()
        if char_filter == []:
            self.project_names_to_display = self.project_names.copy()
            self.project_names_raw = self.project_names_to_display.copy()
            self.endResetModel()
            self.tv.selectRow(0)
            return

        for project_name in self.project_names:
            j = 0
            new_label = ""
            for i in range(len(project_name)):
                if (
                    j < len(char_filter)
                    and char_filter[j].lower() == project_name[i].lower()
                ):
                    j += 1
                    new_label += f'<span style="background-color: pink; color: #000000;">{project_name[i]}</span>'
                else:
                    new_label += project_name[i]
            if j == len(char_filter):
                self.project_names_to_display.append(new_label)
                self.project_names_raw.append(project_name)

        self.endResetModel()
        self.tv.selectRow(0)

    def headerData(self, section, orientation, /, role=...) -> Any:
        return None

    def rowCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return len(self.project_names_to_display)

    def columnCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return 1

    def data(
        self, index: QModelIndex | QPersistentModelIndex, /, role: int = ...
    ) -> Any:
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return self.project_names_to_display[index.row()]
        else:
            return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled


class ProjectTableView(QTableView):
    def __init__(
        self,
        app: App,
        selection_filter_changed: Callable[[list[str]], None],
        open_project: Callable[[], None],
        close_dialog: Callable[[], Any],
    ):
        super().__init__(None)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().hide()
        self.select_chars = []
        self.projects_model = ProjectsModel(self, app)
        self.setModel(self.projects_model)
        self.setItemDelegate(Txt2HTMLDelegate())
        self.selection_filter_changed = selection_filter_changed
        self.open_project = open_project
        self.close_dialog = close_dialog

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        super().mouseDoubleClickEvent(event)
        self.open_project()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        event_key = event.key()
        match event_key:
            case Qt.Key.Key_Escape:
                if self.select_chars == []:
                    self.close_dialog()
                else:
                    self.select_chars.clear()
                    self.projects_model.apply_filter(self.select_chars)
                    self.selection_filter_changed(self.select_chars)
            case Qt.Key.Key_Backspace:
                self.select_chars = self.select_chars[:-1]
                self.projects_model.apply_filter(self.select_chars)
                self.selection_filter_changed(self.select_chars)
            case Qt.Key.Key_Return:
                self.open_project()
            case _:
                ch = event.text()
                if PROJECT_VALID_CHAR_RE.match(ch):
                    self.select_chars.append(ch)
                    self.projects_model.apply_filter(self.select_chars)
                    self.selection_filter_changed(self.select_chars)
                else:
                    super().keyPressEvent(event)


class OpenProjectDialog(Dialog):
    def __init__(self, app: App):
        super().__init__(app.main_window, windowTitle="Open Project", modal=True)
        self.app = app
        self.project_to_open: str | None = None
        self.layout = VBoxLayout()
        self.setLayout(self.layout)
        label = RichTextLabel("Open Project")
        self.layout.addWidget(label)

        def selection_filter_changed(char_filter: list[str]):
            if char_filter == []:
                label.setText("Open Project")
            else:
                label.setText(
                    'Open Project [<span style="background-color: yellow;">'
                    + (",".join(char_filter))
                    + "</span>]"
                )

        def open_project():
            indexes: list[QModelIndex] = self.projects_table.selectedIndexes()
            if len(indexes) == 1:
                project_name_to_open = (
                    self.projects_table.projects_model.project_names_raw[
                        indexes[0].row()
                    ]
                )
                self.project_to_open = project_name_to_open
                self.close()
                app.open_project(project_name_to_open)

        self.projects_table = ProjectTableView(
            app,
            selection_filter_changed=selection_filter_changed,
            open_project=open_project,
            close_dialog=self.close,
        )
        self.projects_table.selectRow(0)
        self.layout.addWidget(self.projects_table)
        self.layout.addWidget(
            HBoxPanel(
                [
                    W(QLabel(), stretch=10),
                    PushButton("Open", on_clicked=open_project),
                    PushButton("Cancel", on_clicked=self.close),
                ]
            )
        )

    @override
    def close(self) -> bool:
        self.app.update_project_selector_current_project(self.app.project.name)
        return super().close()


class NewProjectDialog(Dialog):
    def __init__(self, app: App):
        super().__init__(app.main_window, windowTitle="Create New Project", modal=True)
        self.app = app
        new_project_name = Variable[str]("")

        def create_new_project():
            try:
                app.create_new_project(new_project_name.value)
                self.close()
            except Exception as ex:
                app.show_error(f"{ex}")

        layout = VBoxLayout(
            [
                Label("Create New Project"),
                LineEdit("", min_width=100, reactive_variable=new_project_name),
                HBoxPanel(
                    [
                        W(QLabel(), stretch=10),
                        PushButton("New Project", on_clicked=create_new_project),
                        PushButton("Cancel", on_clicked=self.close),
                    ]
                ),
            ]
        )
        self.setLayout(layout)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        event_key = event.key()
        if event_key == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    @override
    def close(self) -> bool:
        self.app.update_project_selector_current_project(self.app.project.name)
        return super().close()


class SaveAsProjectDialog(Dialog):
    def __init__(self, app: App):
        super().__init__(app.main_window, windowTitle="Save As Project", modal=True)
        self.app = app
        new_project_name = Variable[str]("")

        def create_new_project():
            try:
                app.project.save()
                app.create_copy_of_project(app.project.name, new_project_name.value)
                self.close()
            except Exception as ex:
                app.show_error(f"{ex}")

        self.setLayout(
            VBoxLayout(
                [
                    Label("Create copy of current project"),
                    LineEdit("", min_width=100, reactive_variable=new_project_name),
                    HBoxPanel(
                        [
                            W(QLabel(), stretch=10),
                            PushButton("New Project", on_clicked=create_new_project),
                            PushButton("Cancel", on_clicked=self.close),
                        ]
                    ),
                ]
            )
        )

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        event_key = event.key()
        if event_key == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    @override
    def close(self) -> bool:
        self.app.update_project_selector_current_project(self.app.project.name)
        return super().close()


class DeleteProjectDialog(Dialog):
    def __init__(self, app: App, project_to_delete: str):
        super().__init__(app.main_window, windowTitle="Delete Project?", modal=True)
        self.app = app

        def do_delete():
            self.app.delete_project(project_to_delete)
            self.close()

        self.setLayout(
            VBoxLayout(
                [
                    RichTextLabel(f"Delete Project [<b>{project_to_delete}</b>]?"),
                    HBoxPanel(
                        [
                            PushButton("Yes", on_clicked=do_delete),
                            PushButton("No", on_clicked=self.close),
                            W(QLabel(), stretch=10),
                        ],
                        margins=0,
                    ),
                ]
            )
        )

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        event_key = event.key()
        if event_key == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    @override
    def close(self) -> bool:
        self.app.update_project_selector_current_project(self.app.project.name)
        return super().close()
