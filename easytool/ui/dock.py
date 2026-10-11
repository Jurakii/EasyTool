"""Show the EasyTool panel docked in Maya, tabbed next to the Channel Box.

The workspace control is created already docked, and the panel is built inside it as a Qt child
of Maya's widget, so Maya (not Python) owns it. Creating it floating and moving it afterwards
makes Maya destroy the widget while Python still holds it, which crashes Maya.
"""
import importlib
import sys

from easytool.core.context import AppContext
from easytool.core.paths import maya_cmds
from easytool.qt import QtWidgets, getCppPointer, isValid, wrapInstance

from .panel import EasyToolPanel

CONTROL = "EasyToolWorkspaceControl"
UI_SCRIPT = "import easytool.ui.dock as easytool_dock; easytool_dock.build()"
DOCK_NEXT_TO = ("ChannelBoxLayerEditor", "AttributeEditor")

_panel = None


def panel():
    """The open panel, or None."""
    return _panel if _panel is not None and isValid(_panel) else None


def build(control_ptr=None) -> None:
    """Fill the workspace control. Maya calls this through the control's uiScript."""
    global _panel
    if panel() is not None:
        return
    from maya import OpenMayaUI as omui

    parent_ptr = control_ptr or omui.MQtUtil.getCurrentParent()
    parent = wrapInstance(int(parent_ptr), QtWidgets.QWidget)
    _panel = EasyToolPanel(AppContext(), parent)
    omui.MQtUtil.addWidgetToMayaLayout(int(getCppPointer(_panel)[0]), int(parent_ptr))


def reopen() -> None:
    """Start using a freshly installed EasyTool in this session: close the panel, forget the old code, open the new."""
    cmds = maya_cmds()
    if cmds is None:
        return

    def reload_panel():
        if cmds.workspaceControl(CONTROL, exists=True):
            cmds.deleteUI(CONTROL, control=True)
        for name in [n for n in sys.modules if n == "easytool" or n.startswith("easytool.")]:
            del sys.modules[name]
        importlib.invalidate_caches()
        import easytool  # the new copy

        easytool.show()

    cmds.evalDeferred(reload_panel)  # after the click that asked for it has finished


def show():
    global _panel
    cmds = maya_cmds()
    if cmds is None:
        raise RuntimeError("The docked panel needs Maya's interface. To try it outside Maya, run tools/preview_panel.py.")
    if cmds.workspaceControl(CONTROL, exists=True):
        if panel() is not None:  # already open (Maya also restores it at startup): bring it forward
            cmds.workspaceControl(CONTROL, edit=True, visible=True)
            cmds.workspaceControl(CONTROL, edit=True, r=True)
            return panel()
        cmds.deleteUI(CONTROL, control=True)
    _panel = None  # Maya deletes the old widgets later; don't mistake them for the new panel

    options = dict(label="EasyTool", retain=False, initialWidth=400, widthProperty="preferred", uiScript=UI_SCRIPT)
    target = next(
        (t for t in DOCK_NEXT_TO if cmds.workspaceControl(t, exists=True) and cmds.workspaceControl(t, query=True, visible=True)),
        None,
    )
    if target:
        options["tabToControl"] = (target, -1)
    else:
        options["floating"] = True
    try:
        # build now, even though a new tab starts out behind the Channel Box
        cmds.workspaceControl(CONTROL, loadImmediately=True, **options)
    except TypeError:  # older Maya without loadImmediately
        cmds.workspaceControl(CONTROL, **options)
    if panel() is None:
        from maya import OpenMayaUI as omui

        build(omui.MQtUtil.findControl(CONTROL))
    cmds.workspaceControl(CONTROL, edit=True, r=True)  # "raise": make our tab the active one
    return panel()
