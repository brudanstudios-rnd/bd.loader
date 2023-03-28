from pathlib import Path
import re
from enum import Enum
from functools import partial
from typing import Any, Dict, List, Tuple, Union
import weakref
from typing import Callable, Iterator, Optional, overload

from PySide2 import QtWidgets, QtCore, QtGui, QtSvg
import shiboken2
import qtawesome as qta

from bd.context import Project
from bd.hooks.main import execute as execute_hook
from bd.hooks.exceptions import HooksNotLoadedError, HookNotFoundError

from ..threading_utils import IconManager
from ..data_models import AssetInfo
from ..database.base import DBAccessor


def untokenize(path):
    return path


class EntityType(Enum):
    AssetType = 0
    AssetName = 1


class LoadingStates(Enum):
    ToLoad = 0
    NotLoaded = 1
    InProgress = 2
    Loaded = 3


class ItemRoles:
    ExpandableRole: int = QtCore.Qt.UserRole + 500
    EntityTypeRole: int = QtCore.Qt.UserRole + 501
    DataRole: int = QtCore.Qt.UserRole + 502
    KeyRole: int = QtCore.Qt.UserRole + 503
    LoadingStateRole: int = QtCore.Qt.UserRole + 504


class ItemModel(QtGui.QStandardItemModel):
    def __init__(self, view: QtWidgets.QTreeView, accessor: DBAccessor):
        super().__init__(view)
        self._icon_manager = IconManager(accessor)
        self._icon_manager.start()
        self._asset_icon = qta.icon("fa5s.image")

    def hasChildren(self, index: QtCore.QModelIndex) -> bool:
        if self.data(index, ItemRoles.ExpandableRole):
            return True

        return super().hasChildren(index)

    def data(self, index: QtCore.QModelIndex, role: int) -> Any:
        if index.isValid() and index.column() == 0:
            if role == QtCore.Qt.DecorationRole:
                item: Item = self.itemFromIndex(index)

                if not item.icon():
                    if (
                        item.data(ItemRoles.LoadingStateRole)
                        != LoadingStates.InProgress
                        and item.data(ItemRoles.EntityTypeRole) == EntityType.AssetName
                    ):
                        asset_info = item.data(ItemRoles.DataRole)

                        # if asset_info.icon is None:
                        #     item.setData(
                        #         LoadingStates.Loaded, ItemRoles.LoadingStateRole
                        #     )
                        #     return self._asset_icon

                        item.setData(
                            LoadingStates.InProgress, ItemRoles.LoadingStateRole
                        )

                        def _on_loaded(icon: Union[QtGui.QIcon, None]):
                            if icon and not icon.isNull():
                                item.setIcon(icon)
                            else:
                                item.setIcon(self._asset_icon)

                            item.setData(
                                LoadingStates.Loaded, ItemRoles.LoadingStateRole
                            )

                        self._icon_manager.request_icon(_on_loaded, asset_info)

            elif role == QtCore.Qt.SizeHintRole:
                size = QtCore.QSize(32, 32)

                item: Item = self.itemFromIndex(index)
                if item.data(ItemRoles.EntityTypeRole) == EntityType.AssetName:
                    size.setHeight(64)

                return size

        return super().data(index, role)


class ProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def _human_key(key: str) -> Tuple[Union[str, float]]:
        parts = re.split(r"(\d*\.\d+|\d+)", key)
        return tuple(
            (e.swapcase() if i % 2 == 0 else float(e)) for i, e in enumerate(parts)
        )

    def hasChildren(self, index):
        return self.sourceModel().hasChildren(self.mapToSource(index))

    def filterAcceptsRow(self, source_row, source_parent):
        if not self.filterRegExp().pattern():
            return True

        source_index = self.sourceModel().index(source_row, 0, source_parent)
        data = source_index.data(ItemRoles.KeyRole)

        return self.filterRegExp().indexIn(data) != -1

    def lessThan(self, source_left, source_right):
        left_sort_data = source_left.data(ItemRoles.KeyRole)
        right_sort_data = source_right.data(ItemRoles.KeyRole)
        return self._human_key(left_sort_data) > self._human_key(right_sort_data)


class Item(QtGui.QStandardItem):
    class State(Enum):
        Normal = 0
        Expanded = 1
        Selected = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._icons = {}
        self._state = self.State.Normal

        self.visible = False

    @QtCore.Slot(QtGui.QIcon)  # type: ignore
    def setIcon(self, icon: QtGui.QIcon, state: Optional[State] = None):
        if state is None:
            state = self.State.Normal

        self._icons[state] = icon

        # becomes true if state is None or Normal
        if state == self._state:
            super().setIcon(icon)

    def set_state(self, state: State):
        if state == self._state:
            return

        self._state = state

        icon = self._icons.get(state)
        if icon is not None:
            super().setIcon(icon)


class ItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(
        self,
        loader_render_callback: Callable[[QtGui.QPainter, QtCore.QRect], None],
        parent=None,
    ):
        super().__init__(parent)
        self._loader_render_callback = loader_render_callback

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        source_index = index.model().mapToSource(index)
        item = source_index.model().itemFromIndex(source_index)

        is_decorated = opt.features & QtWidgets.QStyleOptionViewItem.HasDecoration

        opt.features |= QtWidgets.QStyleOptionViewItem.HasDecoration

        if item.data(ItemRoles.EntityTypeRole) == EntityType.AssetName:
            opt.decorationSize = QtCore.QSize(103, 58)

        super().paint(painter, opt, index)

        if item.data(ItemRoles.LoadingStateRole) == LoadingStates.InProgress:
            rect: QtCore.QRect = opt.rect

            decoration_rect = QtCore.QRect(rect.topLeft(), opt.decorationSize)

            bounds = QtCore.QRect(0, 0, 32, 32)
            if is_decorated:
                bounds.moveCenter(rect.center())
                bounds.moveRight(rect.right())
            else:
                bounds.moveCenter(decoration_rect.center())

            self._loader_render_callback(painter, bounds)


class AssetTreeView(QtWidgets.QTreeView):
    class State(Enum):
        Loading = 1
        Ready = 2

    item_clicked = QtCore.Signal(Item)

    def __init__(
        self,
        project: Project,
        accessor: DBAccessor,
        loader_renderer: QtSvg.QSvgRenderer,
        parent=None,
    ):
        super().__init__(parent)
        self._project = project
        self._state = self.State.Loading
        self._accessor = accessor
        self._loader_renderer = loader_renderer

        self._mapping = {}

        self.setHeaderHidden(True)
        self.setIconSize(QtCore.QSize(32, 32))
        self.setItemDelegate(ItemDelegate(self._loader_renderer.render))
        self.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self._model = ItemModel(self, self._accessor)

        self._proxy_model = ProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setRecursiveFilteringEnabled(True)
        self._proxy_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._proxy_model.setDynamicSortFilter(True)

        self.setModel(self._proxy_model)
        self.setSortingEnabled(True)

        self._init_icons()
        self._init_signals()
        self._clear()

    def _init_signals(self):
        self.expanded.connect(self._on_expanded)
        self.collapsed.connect(self._on_collapsed)
        self.clicked.connect(self._on_clicked)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        self.customContextMenuRequested.connect(self._on_menu_requested)

        self._loader_renderer.repaintNeeded.connect(self.viewport().repaint)

    def _init_icons(self):
        folder_color = QtGui.QColor("#1abc9c")  # type: ignore
        asset_type_color = QtGui.QColor("#f1c40f")  # type: ignore
        self._icons = {
            "folder": qta.icon("fa5s.folder", color=folder_color, scale_factor=0.8),
            "folder-open": qta.icon(
                "fa5s.folder-open", color=folder_color, scale_factor=0.8
            ),
            "chr": qta.icon(
                "fa5s.user-astronaut", color=asset_type_color, scale_factor=0.8
            ),
            "prp": qta.icon(
                "fa5s.shopping-bag", color=asset_type_color, scale_factor=0.8
            ),
            "set": qta.icon(
                "fa5s.layer-group", color=asset_type_color, scale_factor=0.8
            ),
            "loc": qta.icon("fa5s.mountain", color=asset_type_color, scale_factor=0.8),
            "asset": qta.icon("fa5s.image", scale_factor=0.8),
        }

    def _clear(self):
        self._model.clear()
        item = self._model.invisibleRootItem()
        item.setData(LoadingStates.NotLoaded, ItemRoles.LoadingStateRole)
        self.state = self.State.Loading
        self._load_children(item)

    def load_by_regex(self, regex: Optional[str] = None):
        if regex:
            self.state = self.State.Loading
            self._load_children_by_regex(regex)
        else:
            self.state = self.State.Ready

        if regex is None:
            regex = ""

        self._proxy_model.setFilterWildcard(regex)

    def _on_expanded(self, parent_index: QtCore.QModelIndex):
        parent_index = self._proxy_model.mapToSource(parent_index)
        parent_item = self._model.itemFromIndex(parent_index)
        parent_item.set_state(Item.State.Expanded)
        self._load_children(parent_item)

    def _on_collapsed(self, parent_index: QtCore.QModelIndex):
        parent_index = self._proxy_model.mapToSource(parent_index)
        parent_item = self._model.itemFromIndex(parent_index)
        parent_item.set_state(Item.State.Normal)

    def _load_children(self, parent_item: Item):
        if parent_item.data(ItemRoles.LoadingStateRole) != LoadingStates.NotLoaded:
            return

        parent_item.setData(LoadingStates.InProgress, ItemRoles.LoadingStateRole)

        if parent_item is self._model.invisibleRootItem():

            def _on_asset_types_loaded(asset_types: List[str]):
                self._append_items(
                    self._model.invisibleRootItem(), EntityType.AssetType, asset_types
                )
                self.state = self.State.Ready

            self._accessor.request_asset_types(_on_asset_types_loaded)

        else:
            asset_query: Union[Dict[str, Union[str, Callable]], None] = None

            entity_type = parent_item.data(ItemRoles.EntityTypeRole)

            if entity_type == EntityType.AssetType:
                asset_query = {"asset_type": parent_item.text()}

            if asset_query:
                asset_query["callback"] = partial(
                    self._append_asset_items, parent_item, EntityType.AssetName
                )
                self._accessor.request_assets(**asset_query)

    def _load_children_by_regex(self, regex: str) -> None:
        self._accessor.request_assets_by_regex(regex, self._append_asset_items_by_regex)

    def _on_clicked(self, prx_index: QtCore.QModelIndex):
        source_index = self._proxy_model.mapToSource(prx_index)
        item = self._model.itemFromIndex(source_index)

        self.item_clicked.emit(item)

        if prx_index.data(ItemRoles.ExpandableRole):
            if not self.isExpanded(prx_index):
                self._load_children(item)
                self.expand(prx_index)
            else:
                self.collapse(prx_index)

    def _on_menu_requested(self, point: QtCore.QPoint) -> None:
        source_index = self._proxy_model.mapToSource(self.currentIndex())
        if not source_index.isValid():
            return

        item = self._model.itemFromIndex(source_index)
        if item.data(ItemRoles.EntityTypeRole) == EntityType.AssetType:
            return

        asset_infos = []

        for index in self.selectedIndexes():
            if index.data(ItemRoles.EntityTypeRole) != EntityType.AssetName:
                continue

            asset_info = index.data(ItemRoles.DataRole)
            asset_infos.append(asset_info)

        menu = QtWidgets.QMenu(self)

        try:
            execute_hook(
                "bd.loader.add_item_menu_action", self._project, menu, asset_infos
            ).all()
        except (HookNotFoundError, HooksNotLoadedError):
            pass
        # button_action = QtWidgets.QAction("Create Reference", self)
        # button_action.setStatusTip("Create Reference")
        # button_action.triggered.connect(lambda: print("CLICKED"))
        # menu.addAction(button_action)

        # TODO: add some actions

        menu.exec_(self.mapToGlobal(point))

    def set_active_project(self, project: Project):
        self._project = project
        self.reload()

    def reload(self) -> None:
        self.collapseAll()
        self.selectionModel().clearSelection()
        self._clear()

    def _find_item_by_key(self, key: str) -> Union[Item, None]:
        child_item_ref = self._mapping.get(key)

        # if an item with that key is not found
        if child_item_ref is not None:
            # dereference the child item
            child_item = child_item_ref()

            if child_item is not None and shiboken2.isValid(child_item):
                return child_item

            del self._mapping[key]

    def _append_items(
        self, parent_item: Item, entity_type: EntityType, labels: List[str]
    ) -> None:
        if not shiboken2.isValid(parent_item):
            return

        for label in labels:
            self._append_item(parent_item, label, entity_type)

        parent_item.setData(LoadingStates.Loaded, ItemRoles.LoadingStateRole)

    def _append_asset_items(
        self, parent_item: Item, entity_type: EntityType, assets: List[AssetInfo]
    ) -> None:
        if not shiboken2.isValid(parent_item):
            return

        for asset in assets:
            item = self._append_item(
                parent_item, asset.name, entity_type, is_expandable=False
            )
            item.setData(asset, ItemRoles.DataRole)

        parent_item.setData(LoadingStates.Loaded, ItemRoles.LoadingStateRole)

    def _append_asset_items_by_regex(self, assets: List[AssetInfo]) -> None:
        for asset in assets:
            asset_name = asset.name
            asset_type = asset.type

            parent_item = self._model.invisibleRootItem()
            parent_key = f"{self._project.id}|{asset_type}"

            asset_type_item = self._find_item_by_key(parent_key)
            if asset_type_item is None:
                asset_type_item = self._append_item(
                    parent_item, asset_type, EntityType.AssetType
                )

            parent_item = asset_type_item

            asset_name_item = self._find_item_by_key("{parent_key}|{asset_name}")
            if asset_name_item is None:
                child_item = self._append_item(
                    parent_item, asset_name, EntityType.AssetName, is_expandable=False
                )
                child_item.setData(asset, ItemRoles.DataRole)

        self.state = self.State.Ready

    def _append_item(
        self,
        parent_item: Item,
        label: str,
        entity_type: EntityType,
        key: Optional[str] = None,
        is_expandable: bool = True,
    ) -> Item:
        if not shiboken2.isValid(parent_item):
            parent_item = self._model.invisibleRootItem()

        parent_key = parent_item.data(ItemRoles.KeyRole)
        if not parent_key:
            parent_key = str(self._project.id)

        key = f"{parent_key}|{key or label}"

        child_item = self._find_item_by_key(key)
        if child_item is not None:
            return child_item

        child_item = Item(label)

        child_item.setData(entity_type, ItemRoles.EntityTypeRole)
        child_item.setData(is_expandable, ItemRoles.ExpandableRole)
        child_item.setData(key, ItemRoles.KeyRole)
        child_item.setData(LoadingStates.NotLoaded, ItemRoles.LoadingStateRole)
        child_item.setData(label, ItemRoles.DataRole)

        child_item.setEditable(False)

        self._mapping[key] = weakref.ref(child_item)

        parent_item.appendRow(child_item)

        if entity_type == EntityType.AssetName:
            return child_item

        if entity_type == EntityType.AssetType:
            if label == "Character":
                child_item.setIcon(self._icons["chr"])
            elif label == "Environment":
                child_item.setIcon(self._icons["loc"])
            elif label == "Prop":
                child_item.setIcon(self._icons["prp"])
            elif label == "Set":
                child_item.setIcon(self._icons["set"])
        else:
            child_item.setIcon(self._icons["folder"], state=child_item.State.Normal)
            child_item.setIcon(
                self._icons["folder-open"], state=child_item.State.Expanded
            )

        return child_item

    @property
    def state(self) -> State:
        return self._state

    @state.setter
    def state(self, state: State) -> None:
        if state == self._state:
            return

        self._state = state

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        if self._state == self.State.Loading:
            painter = QtGui.QPainter(self.viewport())
            rect = self.viewport().rect()
            bounds = QtCore.QRect(0, 0, 64, 64)
            bounds.moveCenter(rect.center())
            self._loader_renderer.render(painter, bounds)
        else:
            return super().paintEvent(event)


class AssetSelectorWidget(QtWidgets.QWidget):
    item_clicked = QtCore.Signal(Item)

    def __init__(
        self,
        project: Project,
        accessor: DBAccessor,
        loader_renderer: QtSvg.QSvgRenderer,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._project = project
        self._accessor = accessor
        self._loader_renderer = loader_renderer

        self._init_widgets()
        self._init_signals()
        self._init_layout()

    def _init_widgets(self):
        self._tree_view = AssetTreeView(
            self._project, self._accessor, self._loader_renderer, self
        )

        self._filter = QtWidgets.QLineEdit(self)
        self._filter.setMinimumHeight(32)
        self._filter.setPlaceholderText("Filter")
        self._filter.setStyleSheet("padding-left: 8px")
        self._filter.setFocus()  # type: ignore

    def _init_signals(self):
        self._tree_view.item_clicked.connect(self.item_clicked)
        self._filter.textChanged.connect(self._on_filter_changed)
        self._filter.returnPressed.connect(self._on_filter_return_pressed)

    def _init_layout(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._filter)
        layout.addWidget(self._tree_view)
        layout.setContentsMargins(0, 0, 0, 0)  # type: ignore

    def _on_filter_changed(self, new_text: str):
        if not new_text:
            self._tree_view.load_by_regex()

    def _on_filter_return_pressed(self):
        self._tree_view.load_by_regex(self._filter.text())

    def set_active_project(self, project):
        self._filter.clear()
        self._tree_view.set_active_project(project)
