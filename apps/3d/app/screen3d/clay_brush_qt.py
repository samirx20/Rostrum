"""The Clay tool's brush rows (Size, Strength, Falloff, Spacing, Mirror, Front faces only) (clay_tool_qt.py), for QML as `viewport.clay.brushObj`: the selected clay's
own brush fields (rostrum3d fields, group "Brush"; CL1 CONTRACT § 1) drawn by the kit's InspectorRow exactly as it
draws any field. The values live on the clay (they are the next stroke's settings; each stroke step keeps its own copy),
so an edit is the bridge's own `clay.set` (one undo step; a scrub is one gesture), the same call an agent makes.
The brush itself (the seven tiles, Mask among them) is drawn by ClayPanel.qml, not here. The kit's layout puts the main
rows first (Size, Strength, Mirror), then the finer ones (Falloff, Spacing, Front faces only).
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum3d import fields as F
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

ROWS = ("brushSize", "brushStrength", "brushFalloff", "brushSpacing", "symmetry", "frontOnly")


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
        # the screen's facts (bridge_rows.facts_of), not none: the rows are valid only while `sculpting` (CL1b: with {}
        # that fact read as off and Size, Strength and Mirror vanished from the Clay panel)
        # update, not reset: a stroke's new step changes no brush row, and rebuilding all six rows' controls on every
        # document change was the longest part of letting go of a stroke (3d-v3: ~30 ms of the GUI thread)
        self.model.update(rows.evaluate(self._static, it, self.b.facts_of(it), False) if it is not None and self._static else [])
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
