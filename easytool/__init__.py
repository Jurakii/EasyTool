"""EasyTool: install Maya shelf tools from GitHub repos, .zip links and folders."""

__version__ = "0.9.1"


def show():
    """Open the EasyTool panel, docked inside Maya."""
    from easytool.ui.dock import show as _show

    return _show()
