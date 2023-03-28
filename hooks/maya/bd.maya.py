from maya import cmds

from bd.context import get_context
from bd.loader.loader import AssetLibraryWidget


def _get_main_window():
    import sys
    import maya.OpenMayaUI as omui
    from PySide2 import QtWidgets
    from shiboken2 import wrapInstance

    _type = int if sys.version_info.major > 2 else long
    return wrapInstance(_type(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)


def _show_loader(logger):
    context = get_context()
    if not context:
        logger.warning("Unable to publish with no active Context defined!")
        return

    task = context.task
    if not task:
        logger.warning("Unable to publish with no active Task defined!")
        return

    dlg = AssetLibraryWidget(_get_main_window())
    dlg.show()


def _add_publish_shelf_button(shelf, logger):
    if not shelf.endswith("BDPipeline"):
        return

    cmds.shelfButton(
        image="bd.loader.svg",
        label="Loader",
        annotation="Loader",
        command=lambda: _show_loader(logger),
        sourceType="python",
        parent=shelf,
    )


def register(registry):
    registry.add_hook("bd.maya.add_shelf_buttons", _add_publish_shelf_button)
