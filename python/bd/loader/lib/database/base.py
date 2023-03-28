from typing import Callable, List, Optional, Union

from PySide2 import QtGui, QtCore

from bd.context import Project

from ..data_models import AssetInfo, AssetDetails


class DBAccessor(QtCore.QObject):
    def set_active_project(self, project: Project) -> None:
        raise NotImplementedError()

    def request_asset_types(self, callback: Callable[[List[str]], None]) -> None:
        raise NotImplementedError()

    def request_assets(
        self, asset_type: str, callback: Callable[[List[AssetInfo]], None]
    ) -> None:
        raise NotImplementedError()

    def request_assets_by_regex(
        self, regex: str, callback: Callable[[List[AssetInfo]], None]
    ) -> None:
        raise NotImplementedError()

    def request_asset_details(
        self,
        asset_info: AssetInfo,
        callback: Callable[[Union[AssetDetails, None]], None],
    ):
        raise NotImplementedError()

    def load_asset_icon_pixmap(
        self, asset_info: AssetInfo
    ) -> Union[QtGui.QPixmap, None]:
        raise NotImplementedError()
