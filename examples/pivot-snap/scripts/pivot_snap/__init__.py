"""Pivot Snap: move the pivots of the selected objects."""
from maya import cmds


def _selected():
    nodes = cmds.ls(selection=True, transforms=True, long=True) or []
    if not nodes:
        cmds.warning("Pivot Snap: select one or more objects first.")
    return nodes


def to_center():
    for node in _selected():
        cmds.xform(node, centerPivots=True)


def to_bottom():
    for node in _selected():
        x0, y0, z0, x1, _y1, z1 = cmds.exactWorldBoundingBox(node)
        cmds.xform(node, worldSpace=True, pivots=((x0 + x1) / 2.0, y0, (z0 + z1) / 2.0))


def to_origin():
    for node in _selected():
        cmds.xform(node, worldSpace=True, pivots=(0, 0, 0))
