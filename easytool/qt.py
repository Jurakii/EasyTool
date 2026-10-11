"""Qt bindings for both Maya generations: PySide6 (Maya 2025+) and PySide2 (Maya 2022-2024)."""
try:
    from PySide6 import QtCore, QtGui, QtSvg, QtWidgets
    from shiboken6 import getCppPointer, isValid, wrapInstance

    QAction = QtGui.QAction
    QT_MAJOR = 6
except ImportError:
    from PySide2 import QtCore, QtGui, QtSvg, QtWidgets
    from shiboken2 import getCppPointer, isValid, wrapInstance

    QAction = QtWidgets.QAction
    QT_MAJOR = 5

Signal = QtCore.Signal


def exec_(obj, *args):
    """Run a dialog or menu modally on either binding."""
    run = getattr(obj, "exec", None) if QT_MAJOR == 6 else getattr(obj, "exec_")
    return run(*args)


__all__ = [
    "QtCore", "QtGui", "QtSvg", "QtWidgets", "QAction", "QT_MAJOR", "Signal",
    "exec_", "getCppPointer", "isValid", "wrapInstance",
]
