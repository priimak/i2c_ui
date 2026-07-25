from PySide6.QtCore import QAbstractTableModel, QTimer, QModelIndex
from PySide6.QtGui import Qt, QColor
from PySide6.QtWidgets import QTableView, QAbstractItemView, QMenu
from i2cdgui.app import App


class ResultsTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.highlighted_row = -1
        self.loading_highlight_color = QColor("lightgreen")
        self.default_row_color = QColor("white")

    def headerData(self, section, orientation, /, role=...):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            match section:
                case 0:
                    return "Name/Addr"
                case 1:
                    return "Val(Hex)"
                case 2:
                    return "Val(Bin)"
                case _:
                    return ""
        elif orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return None
        else:
            return super().headerData(section, orientation, role)

    def rowCount(self, index):
        return len(self.rows)

    def columnCount(self, index):
        return 3

    def data(self, index, role: int):
        if index.isValid():
            if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
                return self.rows[index.row()][index.column()]
            elif role == Qt.ItemDataRole.BackgroundRole:
                return self.loading_highlight_color if index.row() == self.highlighted_row else self.default_row_color

    def setData(self, index, value, role):
        if role == Qt.ItemDataRole.EditRole:
            self.rows[index.row()][index.column()] = value
            return True
        else:
            return False

    def flags(self, index):
        return (Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

    def indexOfByAddr(self, address: str) -> int:
        """ Returns row where register value for register address is to be found or -1 if it is not present anywhere """
        try:
            return [row[0] for row in self.rows].index(address)
        except ValueError:
            return -1


class ResultsPanel(QTableView):
    def __init__(self, app: App):
        super().__init__(None)
        self.app = app
        self.horizontalHeader().setStretchLastSection(True)
        self.model = ResultsTableModel()
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setModel(self.model)
        self.doubleClicked.connect(self.re_read_register)

        self.context_menu = QMenu(self)
        self.context_menu.addAction("Define register")
        self.context_menu.addAction("Re-read from device")

        self.context_menu.addAction("Remove from results panel", self.remove_select_reg_result)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.context_menu.popup(self.viewport().mapToGlobal(pos)))

    def remove_select_reg_result(self):
        idx = self.currentIndex()
        if idx is not None:
            self.model.beginResetModel()
            self.model.rows.pop(idx.row())
            self.model.endResetModel()

    def re_read_register(self, index: QModelIndex):
        self.app.read_register_at_addr(int(self.model.rows[index.row()][0], 16))

    def off_highlight(self):
        self.model.beginResetModel()
        self.model.highlighted_row = -1
        self.model.endResetModel()

    def show_register_value(self, address: str, hexval: str, binval: str) -> None:
        row = self.model.indexOfByAddr(address)
        self.model.beginResetModel()
        if row == -1:
            # insert new row
            self.model.rows.append([address, hexval, binval])
            self.model.rows.sort(key=lambda x: int(x[0], 16))
            self.model.highlighted_row = self.model.indexOfByAddr(address)
        else:
            self.model.highlighted_row = row
            self.model.rows[row] = [address, hexval, binval]
        QTimer.singleShot(250, self.off_highlight)
        self.model.endResetModel()
