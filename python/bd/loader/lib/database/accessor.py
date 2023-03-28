from typing import Callable, List, Optional, Union

from PySide2 import QtGui

from bd.hooks.main import execute as execute_hook
from bd.hooks.exceptions import HooksNotLoadedError, HookNotFoundError
from bd.context import Project

from ..data_models import AssetInfo, AssetDetails
from ..threading_utils import RequestRunnable
from .base import DBAccessor


class Accessor(DBAccessor):
    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None

    def set_active_project(self, project: Project) -> None:
        self._project = project

    def request_asset_types(self, callback: Callable[[List[str]], None]) -> None:
        if self._project is None:
            return

        def _request() -> List[str]:
            result = []
            try:
                result = (
                    execute_hook("bd.loader.get_asset_types", self._project).one()
                    or result
                )
            except (HookNotFoundError, HooksNotLoadedError):
                pass
            return result

        RequestRunnable.execute(_request, callback)

    def request_assets(
        self, asset_type: str, callback: Callable[[List[AssetInfo]], None]
    ) -> None:
        if self._project is None:
            return

        def _request() -> List[AssetInfo]:
            result = []
            try:
                result = (
                    execute_hook(
                        "bd.loader.get_assets", self._project, asset_type
                    ).one()
                    or result
                )
            except (HookNotFoundError, HooksNotLoadedError):
                pass
            return result

        RequestRunnable.execute(_request, callback)

    def request_assets_by_regex(
        self, regex: str, callback: Callable[[List[AssetInfo]], None]
    ) -> None:
        if not self._project:
            return

        def _request() -> List[AssetInfo]:
            result = []
            try:
                result = (
                    execute_hook(
                        "bd.loader.get_assets_by_regex", self._project, regex
                    ).one()
                    or result
                )
            except (HookNotFoundError, HooksNotLoadedError):
                pass
            return result

        RequestRunnable.execute(_request, callback)

    def request_asset_details(
        self,
        asset_info: AssetInfo,
        callback: Callable[[Union[AssetDetails, None]], None],
    ):
        if self._project is None:
            return

        def _request() -> Union[AssetDetails, None]:
            try:
                return execute_hook(
                    "bd.loader.get_assets_details", self._project, asset_info
                ).one()
            except (HookNotFoundError, HooksNotLoadedError):
                pass

        RequestRunnable.execute(_request, callback)

    def load_asset_icon_pixmap(
        self, asset_info: AssetInfo
    ) -> Union[QtGui.QPixmap, None]:
        try:
            return execute_hook(
                "bd.loader.load_asset_icon_pixmap", self._project, asset_info
            ).one()
        except (HookNotFoundError, HooksNotLoadedError):
            pass
