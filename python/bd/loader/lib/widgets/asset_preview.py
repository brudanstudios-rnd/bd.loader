from typing import Union
from PySide2 import QtWidgets, QtCore, QtGui


class AssetPreviewWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Union[QtGui.QPixmap, None] = None
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self.setAutoFillBackground(False)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "background-color: hsv(0, 0, 45); "
            "border: 1px solid hsv(0, 0, 52); "
            "border-radius: 4px;"
        )
        self.setMinimumHeight(128)
        self.setMinimumWidth(128)

    def sizeHint(self):
        return QtCore.QSize(1000, 1000)

    def clear(self):
        self._pixmap = None
        self.update()

    def set_pixmap(self, pixmap):
        self._pixmap = pixmap
        self.repaint()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)

        if self._pixmap is not None:
            painter = QtGui.QPainter(self)

            rect = self.rect()
            size = self.size().shrunkBy(QtCore.QMargins(2, 2, 2, 2))
            self.style().drawItemPixmap(
                painter,
                rect,
                QtCore.Qt.AlignCenter,
                self._pixmap.scaled(
                    size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
                ),
            )
