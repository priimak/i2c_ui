from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, Qt
from PySide6.QtWidgets import QAbstractItemView, QTableView, QWidget
from pytide6 import ComboBox, HBoxPanel, Label, Menu, PushButton, VBoxPanel, W

from i2cdgui.app import App
from i2cdgui.i2c_op_thread import HighlightOff, ReadRegister, RequestReadAllRegisters
from i2cdgui.project import Project
from i2cdgui.reg_read_results import ShowRegSignalData


class ResultsTableModel(QAbstractTableModel):
    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.highlighted_rows: set[int] = set()
        self.loading_highlight_color = QColor("lightgreen")
        self.default_row_color = QColor("white")

    @property
    def project(self) -> Project:
        return self.app.project

    def headerData(self, section, orientation, /, role=...):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            match section:
                case 0:
                    return "Name/Addr"
                case 1:
                    return "Val(Hex)"
                case 2:
                    return "Val(Bin)"
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
        return len(self.project.results)

    def columnCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return 3

    def data(
        self, index: QModelIndex | QPersistentModelIndex, /, role: int = ...
    ) -> Any:
        if index.isValid():
            if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
                return self.project.get_results_at_index(index.row())[index.column()]
            elif role == Qt.ItemDataRole.BackgroundRole:
                return (
                    self.loading_highlight_color
                    if index.row() in self.highlighted_rows
                    else self.default_row_color
                )
            else:
                return None
        else:
            return None

    def setData(
        self, index: QModelIndex | QPersistentModelIndex, value: Any, role: int = ...
    ) -> bool:
        if role == Qt.ItemDataRole.EditRole:
            self.project.get_results_at_index(index.row())[index.column()] = value
            return True
        else:
            return False

    def flags(self, index: QModelIndex | QPersistentModelIndex):
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def indexOfByAddr(self, address: str) -> int:
        """Returns row where register value for register address is to be found or -1 if it is not present anywhere"""
        return self.project.get_results_index_of_by_addr(address)


class ResultsTable(QTableView):
    def __init__(
        self,
        app: App,
        reloading_on: Callable[[], None],
        reloading_off: Callable[[], None],
    ):
        super().__init__(None)
        self.app = app
        self.horizontalHeader().setStretchLastSection(True)
        self.model = ResultsTableModel(app)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setModel(self.model)
        self.doubleClicked.connect(self.re_read_register)

        self.context_menu = Menu(
            parent=self,
            actions=[
                ("Define register", lambda: None),
                ("Re-read from device", self.re_read_selected_register),
                ("Remove from results panel", self.remove_select_reg_result),
            ],
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.context_menu.popup(self.viewport().mapToGlobal(pos))
        )
        self.reloading_on = reloading_on
        self.reloading_off = reloading_off
        self.app.connect_re_read_all_registers(self.re_read_all_registers)
        self.app.connect_highlight_off(self.off_highlight)
        self.app.connect_highlight_register_at_addr(self.highlight_at_addr)
        self.viewport().setMouseTracking(True)

        self.app.request_results_reload = self.request_results_reload

    def re_read_selected_register(self):
        for index in self.selectedIndexes():
            row = self.model.project.get_results_at_index(index.row())
            self.app.re_read_register_at_addr(
                reg_addr=int(row[0], 16), num_bytes=int(len(row[2]) / 8)
            )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        match event.key():
            case Qt.Key.Key_Delete:
                self.remove_select_reg_result()
            case Qt.Key.Key_Return | Qt.Key.Key_Enter:
                self.re_read_selected_register()
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        row = self.rowAt(event.pos().y())
        if row >= 0:
            self.selectRow(row)

    def remove_select_reg_result(self):
        idx = self.currentIndex()
        if idx is not None:
            self.model.beginResetModel()
            self.model.project.remove_result(idx.row())
            self.model.endResetModel()

    def request_results_reload(self):
        self.model.beginResetModel()
        self.model.endResetModel()

    def re_read_register(self, index: QModelIndex):
        row = self.model.project.get_results_at_index(index.row())
        self.app.re_read_register_at_addr(
            reg_addr=int(row[0], 16), num_bytes=int(len(row[2]) / 8)
        )

    def re_read_all_registers(self):
        highlight_individual = self.app.re_read_all_period_millis == -1
        if not highlight_individual:
            self.app.toggle_reloading_label_highlight()
        for row in self.model.project.results:
            self.app.op_thread.commands.put(
                ReadRegister(
                    device_address=self.app.device_address,
                    register_address=int(row[0], 16),
                    num_bytes=int(len(row[2]) / 8),
                    highlight=highlight_individual,
                )
            )

        if self.app.re_read_all_period_millis > 0:
            self.app.op_thread.commands.put(
                RequestReadAllRegisters(delay_millis=self.app.re_read_all_period_millis)
            )
        else:
            self.app.op_thread.commands.put(HighlightOff(delay_millis=300))

    def off_highlight(self):
        self.model.beginResetModel()
        self.model.highlighted_rows.clear()
        self.model.endResetModel()

    def highlight_at_addr(self, register_address: str):
        row_to_highlight = self.model.indexOfByAddr(register_address)
        if row_to_highlight < 0:
            self.off_highlight()
        else:
            self.model.beginResetModel()
            self.model.highlighted_rows.add(row_to_highlight)
            self.model.endResetModel()

    def show_register_value(self, data: ShowRegSignalData) -> None:
        row = self.model.indexOfByAddr(data.register_address)
        self.model.beginResetModel()
        if row == -1:
            # insert new row
            self.model.project.add_result(
                [data.register_address, data.hexval, data.binval]
            )
            row = self.model.indexOfByAddr(data.register_address)
        else:
            self.model.project.replace_result(
                row, [data.register_address, data.hexval, data.binval]
            )

        if data.highlight:
            self.model.highlighted_rows.add(row)
        self.model.endResetModel()


class ResultsPanel(VBoxPanel):
    def __init__(self, app: App):
        super().__init__()
        self.app = app

        def freq_change(frequency_text: str) -> None:
            match frequency_text:
                case "every 0.25s":
                    app.re_read_all_period_millis = 250
                case "every 0.5s":
                    app.re_read_all_period_millis = 500
                case "every 1s":
                    app.re_read_all_period_millis = 1000
                case _:
                    app.re_read_all_period_millis = -1
                    app.reloading_label_highlight_off()

        # period_selector = ComboBox(items=["once", "every 0.25s", "every 0.5s", "every 1s"], on_text_change=freq_change)
        # period_selector.setStyleSheet("background-color: white")
        self.re_reading_label = Label("    ")
        self.re_reading_label.setProperty("on", False)

        self.app.toggle_reloading_label_highlight = (
            self.toggle_reloading_label_highlight
        )

        def reloading_on():
            self.re_reading_label.setStyleSheet("background-color: green")

        def reloading_off():
            self.re_reading_label.setStyleSheet("")
            self.re_reading_label.setProperty("on", False)

        self.app.reloading_label_highlight_off = reloading_off

        results_table = ResultsTable(app, reloading_on, reloading_off)
        self.addWidgets(
            HBoxPanel(
                [
                    PushButton(
                        "Re-Read All", on_clicked=results_table.re_read_all_registers
                    ),
                    ComboBox(
                        items=["once", "every 0.25s", "every 0.5s", "every 1s"],
                        on_text_change=freq_change,
                    ),
                    self.re_reading_label,
                    W(QWidget(), stretch=2),
                ],
                background_color="lightblue",
            ),
            results_table,
        )
        self.remove_select_reg_result = results_table.remove_select_reg_result
        self.re_read_register = results_table.re_read_register
        self.off_highlight = results_table.show_register_value
        self.show_register_value = results_table.show_register_value
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)

    def toggle_reloading_label_highlight(self):
        if self.re_reading_label.property("on"):
            self.re_reading_label.setStyleSheet("")
            self.re_reading_label.setProperty("on", False)
        else:
            self.re_reading_label.setStyleSheet("background-color: green")
            self.re_reading_label.setProperty("on", True)
