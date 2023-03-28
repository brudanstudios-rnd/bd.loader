import logging
from typing import Callable, Dict, List, Union
from queue import LifoQueue, Empty

from PySide2 import QtCore, QtGui

from .data_models import AssetInfo
from .database.base import DBAccessor

log = logging.getLogger(__name__)

IconRequestCallback = Callable[[QtGui.QIcon], None]


class InvokeMethod(QtCore.QObject):
    """Invokes a callable on a main thread."""

    def __init__(self, method: Callable):
        super().__init__()

        main_thread = QtGui.QGuiApplication.instance().thread()
        self.moveToThread(main_thread)
        self.setParent(QtGui.QGuiApplication.instance())
        self.method = method
        self.called.connect(self.execute)  # type: ignore
        self.called.emit()  # type: ignore

    called = QtCore.Signal()

    @QtCore.Slot()  # type: ignore
    def execute(self):
        self.method()
        # trigger garbage collector
        self.setParent(None)  # type: ignore


class PixmapLoader(QtCore.QObject):
    pixmap_loaded = QtCore.Signal(AssetInfo, QtGui.QPixmap)

    def __init__(self, accessor: DBAccessor, queue: "LifoQueue[AssetInfo]"):
        super().__init__()
        self._accessor = accessor
        self._queue = queue
        self._running: bool = True
        self._icon_rect = QtCore.QRect(0, 0, 103, 58)

    def _create_rounded_pixmap(self, pixmap: QtGui.QPixmap):
        """

        AI is creating summary for _create_rounded_pixmap
        Args:
            pixmap: Hello world
        """
        # min_side = min(pixmap.height(), pixmap.width())

        target_rect = QtCore.QRect(0, 0, pixmap.width(), pixmap.height())
        # target_rect = QtCore.QRect(0, 0, min_side, min_side)
        target_rect.moveCenter(pixmap.rect().center())

        pixmap = pixmap.copy(target_rect).scaledToHeight(
            self._icon_rect.width(), QtCore.Qt.SmoothTransformation
        )

        rounded_pixmap = QtGui.QPixmap(self._icon_rect.size())
        rounded_pixmap.fill(QtCore.Qt.transparent)

        clip_path = QtGui.QPainterPath()
        clip_path.addRoundedRect(self._icon_rect, 4, 4)

        painter = QtGui.QPainter(rounded_pixmap)

        painter.setRenderHint(painter.Antialiasing)

        painter.setClipPath(clip_path)

        painter.drawPixmap(self._icon_rect, pixmap)

        return rounded_pixmap

    def start(self) -> None:
        while self._running:
            try:
                asset_info = self._queue.get(timeout=0.005)
            except Empty:
                continue

            try:
                pixmap = self._accessor.load_asset_icon_pixmap(asset_info)
                if pixmap:
                    pixmap = self._create_rounded_pixmap(pixmap)

                self.pixmap_loaded.emit(asset_info, pixmap)

            except Exception as e:
                log.exception(f"Unable to load the asset icon ({asset_info}): ")

    def stop(self):
        self._running = False


class IconManager(QtCore.QObject):
    def __init__(self, accessor: DBAccessor, parent=None):
        super().__init__(parent)
        self._accessor = accessor
        self._queue: "LifoQueue[AssetInfo]" = LifoQueue()
        self._pixmap_loaders: List[PixmapLoader] = []
        self._pixmap_loader_threads: List[QtCore.QThread] = []
        self._loaded_icons: Dict[Union[int, str], QtGui.QIcon] = {}
        self._requests: Dict[Union[int, str], IconRequestCallback] = {}

    def start(self):
        for i in range(12):
            pixmap_loader = PixmapLoader(self._accessor, self._queue)
            pixmap_loader_thread = QtCore.QThread()

            pixmap_loader.moveToThread(pixmap_loader_thread)

            pixmap_loader_thread.started.connect(pixmap_loader.start)
            pixmap_loader_thread.finished.connect(pixmap_loader_thread.deleteLater)
            pixmap_loader_thread.finished.connect(pixmap_loader_thread.deleteLater)

            pixmap_loader.pixmap_loaded.connect(self._on_pixmap_loaded)

            QtCore.QCoreApplication.instance().aboutToQuit.connect(self._stop_loader)

            pixmap_loader_thread.start()

            self._pixmap_loaders.append(pixmap_loader)
            self._pixmap_loader_threads.append(pixmap_loader_thread)

    def _stop_loader(self):
        """Stop the icon loader thread."""
        for pixmap_loader, pixmap_loader_thread in zip(
            self._pixmap_loaders, self._pixmap_loader_threads
        ):
            pixmap_loader.stop()
            if pixmap_loader_thread:
                pixmap_loader_thread.exit()
                pixmap_loader_thread.wait()  # type: ignore

    def request_icon(
        self, callback: IconRequestCallback, asset_info: AssetInfo
    ) -> None:
        """Send an icon request to the queue.

        Args:
            callback (IconRequestCallback): model item to set the icon for.
            asset_info (int): asset info to request the icon from.
        """
        asset_id = asset_info.id

        if asset_id in self._loaded_icons:
            return callback(self._loaded_icons[asset_id])

        if asset_id in self._requests:
            return

        self._requests[asset_id] = callback

        self._queue.put_nowait(asset_info)

    def _on_pixmap_loaded(self, asset_info: AssetInfo, pixmap: QtGui.QPixmap) -> None:
        icon = QtGui.QIcon(pixmap)
        self._loaded_icons[asset_info.id] = icon
        self._apply_icon(asset_info.id)

    def _apply_icon(self, asset_id: Union[int, str]) -> None:
        icon = self._loaded_icons[asset_id]
        callback = self._requests.get(asset_id)
        if callback:
            callback(icon)

    def clear_cache(self):
        if self._loaded_icons:
            self._loaded_icons.clear()
        if self._requests:
            self._requests.clear()


class RequestRunnable(QtCore.QRunnable):
    def __init__(self, request: Callable, callback: Callable):
        super().__init__()
        self._request = request
        self._callback = callback
        self.setAutoDelete(True)

    def run(self):
        try:
            result = self._request()
            InvokeMethod(lambda: self._callback(result))
        except Exception as e:
            log.exception(f"Unable to make request '{self._request}' due to error:")

    @classmethod
    def execute(cls, request: Callable, callback: Callable) -> None:
        runner = cls(request, callback)
        QtCore.QThreadPool.globalInstance().start(runner)
