import os
from pathlib import Path
from typing import Union

from PySide2 import QtWidgets, QtCore, QtGui, QtSvg

import qtawesome as qta

from bd.context import get_context

from ..database.accessor import Accessor

from ..data_models import AssetInfo, AssetDetails
from .asset_selector import AssetSelectorWidget, Item, EntityType, ItemRoles
from .asset_details import AssetDetailsWidget


class AssetLibraryWidget(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_asset_data = None

        self._db_accessor = Accessor()

        self._loader_renderer = QtSvg.QSvgRenderer(":/svg/loader.svg", self)

        self.setWindowTitle("Loader")
        self.setWindowIcon(qta.icon("ei.book", color=QtGui.QColor("#1abc9c")))
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        # self.setMinimumSize(900, 600)
        self.resize(900, 600)

        self._init_widgets()
        self._init_layout()
        self._init_connections()

    def _init_widgets(self):
        project = get_context().project

        self._db_accessor.set_active_project(project)

        self._asset_selector = AssetSelectorWidget(
            project,
            self._db_accessor,
            self._loader_renderer,
        )

        self._asset_details = AssetDetailsWidget(self._loader_renderer)

        self._pb_cancel = QtWidgets.QPushButton("Cancel")

    def _init_layout(self):
        dialogbutton_layout = QtWidgets.QHBoxLayout()
        dialogbutton_layout.addStretch()
        dialogbutton_layout.addWidget(self._pb_cancel)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Horizontal)
        splitter.setContentsMargins(0, 0, 0, 0)

        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.addWidget(self._asset_selector)
        splitter.addWidget(widget)

        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.addWidget(self._asset_details)
        splitter.addWidget(widget)

        splitter.setSizes([self.width() / 2, self.width() / 2])

        main_layout.addWidget(splitter)

        # main_layout.addLayout(dialogbutton_layout)

    def _init_connections(self):
        self._asset_selector.item_clicked.connect(self._on_item_clicked)

        self._pb_cancel.clicked.connect(self.close)

    def _on_item_clicked(self, item: Item):
        entity_type = item.data(ItemRoles.EntityTypeRole)

        if entity_type != EntityType.AssetName:
            self._asset_details.reload()
        else:
            asset_info: AssetInfo = item.data(ItemRoles.DataRole)
            self._current_asset_info = asset_info

            if asset_info.details is not None:
                self._asset_details.reload(asset_info.details)

            else:
                self._asset_details.state = AssetDetailsWidget.State.Loading

                def _on_asset_details_received(
                    asset_details: Union[AssetDetails, None]
                ):
                    asset_info.details = asset_details

                    # 'self._current_asset_info' is alway the latest,
                    # while 'asset_info' is a closure object, created when
                    # _on_item_clicked method was called.
                    # This comparison allows us to ensure that the details view
                    # shows data only for the currently selected item.
                    if self._current_asset_info != asset_info:
                        return

                    self._asset_details.reload(asset_details)

                self._db_accessor.request_asset_details(
                    asset_info, _on_asset_details_received
                )
