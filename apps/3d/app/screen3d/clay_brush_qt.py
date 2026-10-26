"""The Clay tool's Size, Strength and Mirror rows (clay_tool_qt.py), for QML as `viewport.clay.brushObj`: the selected clay's
own brush fields (rostrum3d fields, group "Brush"; CL1 CONTRACT § 1) drawn by the kit's InspectorRow exactly as it
draws any field. The values live on the clay (they are the next stroke's settings; each stroke step keeps its own copy),
so an edit is the bridge's own `clay.set` (one undo step; a scrub is one gesture), the same call an agent makes.
The brush row (Add / Carve / Smooth) is drawn as tiles by ClayPanel.qml, not here.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum3d import fields as F
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

ROWS = ("brushSize", "brushStrength", "symmetry")


class ClayBrush(QObject):
    changed = Signal()

    def __init__(self, tool):
        super().__init__(tool)
        self.t, self.b = tool, tool.b
        params = [p for p in (F.param("clay", n) for n in ROWS) if p is not None]
        self.model = RowsModel(rows.ROLES, self)
        self._static = rows.layout(SimpleNamespace(params=params), "Brush")
        self.refresh()

    def refresh(self):
        it = self.t._item()
        self.model.reset(rows.evaluate(self._static, it, {}, False) if it is not None and self._static else [])
        self.changed.emit()

    rows = Property(QObject, lambda s: s.model, constant=True)

    # --- InspectorRow's bridge: the bridge edits its selection, which is the clay while the brush rows show
    def _mine(self) -> bool:
        return self.t._item() is not None and self.b.selected == self.t.clayId

    @Slot(str, "QVariant", result=bool)
    def setValue(self, name, value):
        return bool(self._mine() and self.b.setValue(name, value))

    @Slot(str)
    def beginScrub(self, name):
        if self._mine():
            self.b.beginScrub(name)

    @Slot(str, "QVariant")
    def scrub(self, name, value):
        if self._mine():
            self.b.scrub(name, value)

    @Slot()
    def endScrub(self):
        self.b.endScrub()

    @Slot()
    def cancelScrub(self):
        self.b.cancelScrub()

    @Slot(str)
    def toggleGroup(self, group):
        pass

    @Slot(str)
    def toggleAnimate(self, name):
        pass                                    # brush settings are still: no key marks
