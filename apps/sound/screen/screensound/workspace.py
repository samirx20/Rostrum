"""The one workspace's screen state (not an edit, never saved in the song): which tool the bottom dock shows
("editor", "mixer" or "" = folded away), how tall the person dragged each tool (0 = the window size's default),
and whether the Library (instruments and sounds) is open on the left. Exposed to QML as `workspace`; the bridge reads
`dock` for "a control once per screen" (onpage.py: the inspector leaves out what the open Mixer shows).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

DOCKS = ("editor", "mixer", "")
OLD_PAGES = {"timeline": "editor", "mix": "mixer", "instruments": ""}     # `page …` in old scripts


class Workspace(QObject):
    changed = Signal()

    def __init__(self, fail, on_dock, parent=None):
        super().__init__(parent)
        self._fail, self._on_dock = fail, on_dock        # bridge._fail; called after the dock changes
        self._dock, self._library = "", False
        self._heights = {"editor": 0, "mixer": 0}

    @Property(str, notify=changed)
    def dock(self):
        return self._dock

    @Property(bool, notify=changed)
    def library(self):
        return self._library

    @Property("QVariantMap", notify=changed)
    def heights(self):
        """{editor, mixer}: the height the person dragged each tool to (0 = not dragged: the size's default)."""
        return dict(self._heights)

    @Slot(str)
    def setDock(self, name):
        name = "" if name == "none" else name
        if name not in DOCKS:
            return self._fail(f'Error: dock: "{name}" is not a dock (editor, mixer or none).')
        if name != self._dock:
            self._dock = name
            self.changed.emit()
            self._on_dock()

    @Slot(str)
    def toggleDock(self, name):
        """E / X: open that tool in the dock, or fold the dock away when it already shows it."""
        self.setDock("" if self._dock == name else name)

    @Slot(str, int)
    def setHeight(self, name, px):
        """The dock's top edge dragged: remembered for that tool (this window only)."""
        if name in self._heights and px != self._heights[name]:
            self._heights[name] = max(0, int(px))
            self.changed.emit()

    @Slot(bool)
    def setLibrary(self, on):
        if on != self._library:
            self._library = on
            self.changed.emit()

    @Slot()
    def toggleLibrary(self):
        self.setLibrary(not self._library)
