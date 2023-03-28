import os
import errno
from typing import Optional

from PySide2 import QtCore, QtGui, QtWidgets


def makedirs(path):
    try:
        os.makedirs(path)
    except OSError as error:
        if error.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

    return path


def open_directory(path):
    """Open a filesystem directory from *path* in the OS file browser.
    If *path* is a file, the parent directory will be opened. Depending on OS
    support the file will be pre-selected.
    """
    if os.path.isfile(path):
        directory = os.path.dirname(path)
    else:
        directory = path

    directory = directory.replace("\\", "/")
    QtGui.QDesktopServices.openUrl(QtCore.QUrl(directory))


def select_directory(title):
    root_dir = QtWidgets.QFileDialog.getExistingDirectory(None, title)
    if root_dir:
        return root_dir
