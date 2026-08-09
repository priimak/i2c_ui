from collections.abc import Callable
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import QIcon, QKeyEvent, QPainter, QTextDocument
from PySide6.QtWidgets import (
    QAbstractItemView,
    QItemDelegate,
    QLineEdit,
    QStyleOptionViewItem,
    QTableView,
)
from pytide6.inputs import LineEdit


class Txt2HTMLDelegate(QItemDelegate):
    def __init__(self) -> None:
        super().__init__()

    def mk_text_document(self, text: str) -> QTextDocument:
        document = QTextDocument()
        document.setHtml(text)
        document.setDocumentMargin(1)
        return document

    def drawDisplay(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        rect: QRect,
        text: str,
        /,
    ) -> None:
        document = self.mk_text_document(text)
        painter.save()
        painter.translate(rect.topLeft())
        document.drawContents(painter)
        painter.restore()

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        data = index.data(Qt.ItemDataRole.DisplayRole)
        return self.mk_text_document(data).size().toSize()


class TableModelWithFilterAction(QAbstractTableModel):
    def apply_filter(self, filter_text: str, post_filter_action: Callable[[], Any]):
        pass


class ListTableView[T: TableModelWithFilterAction](QTableView):
    def __init__(
        self,
        table_model: T,
        pass_key_press_event: Callable[[], Callable[[QKeyEvent], None]],
        on_double_clicked: Callable[[QModelIndex], None] | None,
        hide_horizontal_header: bool = False,
    ):
        super().__init__(None)
        self.pass_key_press_event = pass_key_press_event
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)
        if hide_horizontal_header:
            self.horizontalHeader().hide()
        self.select_chars = []
        self.table_model = table_model
        self.setModel(self.table_model)
        self.setItemDelegate(Txt2HTMLDelegate())

        if on_double_clicked is not None:
            self.doubleClicked.connect(on_double_clicked)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self.pass_key_press_event()(event)


class InTableSearchField[T: TableModelWithFilterAction](LineEdit):
    def __init__(
        self,
        table_view: ListTableView[T],
        on_key_enter: Callable[[QModelIndex], None],
        close_action: Callable[[], Any],
    ):
        super().__init__()
        self.table_view = table_view
        self.on_key_enter = on_key_enter
        self.close_action = close_action

        # place "find" icon on the left side of search text field.
        self.addAction(
            QIcon.fromTheme(QIcon.ThemeIcon.EditFind),
            QLineEdit.ActionPosition.LeadingPosition,
        )

        post_filter_action = lambda: table_view.selectRow(0)
        self.textChanged.connect(
            lambda text: table_view.table_model.apply_filter(text, post_filter_action)
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        event_key = event.key()
        match event_key:
            case Qt.Key.Key_Escape:
                if self.text() == "":
                    self.close_action()
                else:
                    self.setText("")
                    return

            case Qt.Key.Key_Return:
                selected_rows = self.table_view.selectedIndexes()
                self.close_action()
                if selected_rows != []:
                    self.on_key_enter(selected_rows[0])
                return

            case Qt.Key.Key_Down:
                selected_rows = self.table_view.selectedIndexes()
                if selected_rows == []:
                    self.table_view.selectRow(0)
                else:
                    next_row = selected_rows[0].row() + 1
                    if next_row <= self.table_view.table_model.rowCount():
                        self.table_view.selectRow(next_row)
                return

            case Qt.Key.Key_Up:
                selected_rows = self.table_view.selectedIndexes()
                if selected_rows == []:
                    self.table_view.selectRow(0)
                else:
                    next_row = selected_rows[0].row() - 1
                    if next_row >= 0:
                        self.table_view.selectRow(next_row)
                return

        super().keyPressEvent(event)


class TableModelWithOneColumn:
    def columnCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return 1


class TableModelWithTwoColumns:
    def columnCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return 2


class TableModelWithThreeColumns:
    def columnCount(self, /, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return 3


class TableModelWithoutHeader:
    def headerData(self, section, orientation, /, role=...) -> Any:
        return None


class TableModelAllSelectableAndEnabled:
    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled


def apply_filter_to_text(char_filter: list[str], text: str) -> str | None:
    j = 0
    new_text = ""
    char_filter = [c.lower() for c in char_filter]
    num_chars_in_filter = len(char_filter)
    for i in range(len(text)):
        if j < num_chars_in_filter and char_filter[j] == text[i].lower():
            j += 1
            new_text += f'<span style="background-color: pink; color: #000000;">{text[i]}</span>'
        else:
            new_text += text[i]

    return new_text if j == num_chars_in_filter else None
