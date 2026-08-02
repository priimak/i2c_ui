from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import QPainter, QTextDocument
from PySide6.QtWidgets import (
    QItemDelegate,
    QStyleOptionViewItem,
)


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