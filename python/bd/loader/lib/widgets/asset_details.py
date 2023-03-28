from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from PySide2 import QtWidgets, QtCore, QtGui, QtSvg
import arrow

from .asset_preview import AssetPreviewWidget
from ..data_models import AssetDetails


class ResizeSyncFilter(QtCore.QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Resize:
            self.parent().resize(event.size())

        return super().eventFilter(obj, event)


class LoadingOverlay(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, loader_renderer: QtSvg.QSvgRenderer):
        super().__init__(parent)
        self._loader_renderer = loader_renderer
        self._init_ui()
        self._init_connections()

    def _init_ui(self):
        self.setObjectName("LoadingOverlay")

    def _init_connections(self):
        self.parent().installEventFilter(ResizeSyncFilter(self))
        self._loader_renderer.repaintNeeded.connect(self.update)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)

        painter = QtGui.QPainter(self)
        rect = self.rect()
        bounds = QtCore.QRect(0, 0, 64, 64)
        bounds.moveCenter(rect.center())
        self._loader_renderer.render(painter, bounds)


class AssetDetailItem(QtWidgets.QWidget):
    def __init__(
        self, name: str, value: str, parent: Optional[QtWidgets.QWidget] = None
    ):
        super().__init__(parent)
        self._name = name
        self._value = value
        self._init_widgets()
        self._init_layout()

    def _init_widgets(self):
        self._name_label = QtWidgets.QLabel(self._name)
        self._name_label.setStyleSheet("color: grey; font-size: 11px")
        self._value_label = QtWidgets.QLabel(self._value)
        self._value_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._value_label.setMinimumHeight(32)
        self._value_label.setStyleSheet(
            "background-color: hsv(0, 0, 45); "
            "border: 1px solid hsv(0, 0, 52); "
            "border-radius: 4px; "
            "padding-left: 8px"
        )

    def _init_layout(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._name_label)
        layout.addWidget(self._value_label)

    def set_value(self, value):
        self._value = value
        self._value_label.setText(value)

    def clear(self):
        self._value_label.clear()


class AssetDetailsWidget(QtWidgets.QWidget):
    class State(Enum):
        Empty = 0
        Loading = 1
        Ready = 2

    def __init__(self, loader_renderer: QtSvg.QSvgRenderer, parent=None):
        super().__init__(parent)
        self._labels = {}
        self._state = self.State.Empty
        self._current_asset_details: Optional[AssetDetails] = None
        self._loader_renderer = loader_renderer

        self._init_widgets()

    def _init_widgets(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # type: ignore

        self._group = QtWidgets.QFrame(self)
        self._group.hide()

        group_layout = QtWidgets.QVBoxLayout(self._group)
        group_layout.setContentsMargins(0, 0, 0, 8)  # type: ignore
        group_layout.setSpacing(20)  # type: ignore

        self._preview = AssetPreviewWidget()

        self._details = QtWidgets.QWidget()

        details_layout = QtWidgets.QGridLayout(self._details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(12)

        row = -1
        for i, name in enumerate(["name", "version", "created", "modified"]):
            details_item = AssetDetailItem(name.title(), "...")

            column = i % 2

            if i % 2 == 0:
                row += 1

            details_layout.addWidget(details_item, row, column)
            self._labels[name] = details_item

        group_layout.addWidget(self._preview)
        group_layout.addWidget(self._details)
        group_layout.addStretch(1)

        main_layout.addWidget(self._group)

        self._loading_overlay = LoadingOverlay(self._preview, self._loader_renderer)
        self._loading_overlay.hide()

    @property
    def state(self) -> State:
        return self._state

    @state.setter
    def state(self, state: State) -> None:
        if state == self._state:
            return

        if state == self.State.Ready:
            self._loading_overlay.hide()
            self._group.show()
            # self._loader_renderer.repaintNeeded.disconnect(self.update)
        elif state == self.State.Empty:
            self._group.hide()
        else:
            self._group.show()

            self._preview.clear()
            for item in self._labels.values():
                item.clear()

            self._loading_overlay.show()
            # self._loader_renderer.repaintNeeded.connect(self.update)

        self._state = state

    @QtCore.Slot(AssetDetails)  # type: ignore
    def reload(self, asset_details: Optional[AssetDetails] = None):
        if not asset_details:
            self.state = self.State.Empty
        else:
            self._labels["name"].set_value(asset_details.fullname)
            self._labels["version"].set_value(str(asset_details.version))
            self._labels["created"].set_value(
                arrow.get(asset_details.created_at).humanize()
            )
            self._labels["modified"].set_value(
                arrow.get(asset_details.modified_at).humanize()
            )

            thumbnail_pixmap = asset_details.thumbnail
            if thumbnail_pixmap:
                self._preview.set_pixmap(thumbnail_pixmap)
            else:
                self._preview.clear()

            self.state = self.State.Ready

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        if self._state == self.State.Empty:
            painter = QtGui.QPainter(self)
            painter.setPen(QtGui.QColor("grey"))

            options = QtGui.QTextOption()
            options.setWrapMode(QtGui.QTextOption.WordWrap)
            options.setAlignment(QtCore.Qt.AlignCenter)

            painter.drawText(self.rect(), "Select Asset to View the Details", options)
        else:
            super().paintEvent(event)
