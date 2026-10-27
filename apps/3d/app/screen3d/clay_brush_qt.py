"""The Clay tool's brush rows (clay_tool_qt.py), for QML as `viewport.clay.brushObj`: the selected clay's own brush
fields (rostrum3d fields, group "Brush"; CL1 CONTRACT § 1) drawn by the kit's InspectorRow exactly as it draws any
field. The values live on the clay (they are the next stroke's settings; each stroke step keeps its own copy), so an
edit is the bridge's own `clay.set` (one undo step; a scrub is one gesture), the same call an agent makes.
The brush itself (the seven tiles, Mask among them) is drawn by ClayPanel.qml, not here.
Two lists (3d-v4, so the Steps list fits a 900 px high window): `rows`, Size and Strength, always shown; `finer`, the
kit's More fold (closed at first, kept open or closed for the session) with Falloff, Spacing, Front faces only and
Mirror behind it. ClayPanel.qml puts the Steps list between the two.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum3d import fields as F
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

MAIN = ("brushSize", "brushStrength")
FINER = ("brushFalloff", "brushSpacing", "frontOnly", "symmetry")     # behind More, in this order
ROWS = MAIN + FINER


def _params(names, importance=None):
    ps = [p for p in (F.param("clay", n) for n in names) if p is not None]
    return [dataclasses.replace(p, importance=importance) for p in ps] if importance else ps


class ClayBrush(QObject):
    changed = Signal()

    def __init__(self, tool):
        super().__init__(tool)
        self.t, self.b = tool, tool.b
        self.model = RowsModel(rows.ROLES, self)
        self.finer_model = RowsModel(rows.ROLES, self)
        self._static = rows.layout(SimpleNamespace(params=_params(MAIN)), "Brush")
        # all deep: the kit's layout makes the More row and the four behind it
        self._finer = rows.layout(SimpleNamespace(params=_params(FINER, "deep")), "Brush")
        self._more = False                      # the More fold: closed at first, then as left (this session)
        self.refresh()

    def refresh(self):
        it = self.t._item()
        # the screen's facts (bridge_rows.facts_of), not none: the rows are valid only while `sculpting` (CL1b: with {}
        # that fact read as off and Size, Strength and Mirror vanished from the Clay panel)
        facts = self.b.facts_of(it) if it is not None else {}
        self._fill(self.model, rows.evaluate(self._static, it, facts, False) if it is not None and self._static else [])
        self._fill(self.finer_model, rows.evaluate(self._finer, it, facts, self._more) if it is not None and self._finer else [])
        self.changed.emit()

    @staticmethod
    def _fill(model, new):
        # the same rows applying: only their values are patched. A stroke's new step changes no brush row, and
        # rebuilding all six rows' controls on every document change was the longest part of letting go of a stroke
        # (3d-v3: ~30 ms of the GUI thread). Other rows applying (the tool off, another clay): rebuilt, none kept hidden
        shape = lambda rs: [(r.get("id"), r.get("valid", True)) for r in rs]  # noqa: E731
        if new and shape(new) == shape(model.rows):
            model.update(new)
        else:
            model.reset(new)

    rows = Property(QObject, lambda s: s.model, constant=True)            # Size, Strength
    finer = Property(QObject, lambda s: s.finer_model, constant=True)     # More, then Falloff, Spacing, Front, Mirror
    moreOpen = Property(bool, lambda s: s._more, notify=changed)

    @Slot()
    def toggleMore(self):
        """The More row's click: the four rows behind it ease in or out (the kit's model update), nothing rebuilt."""
        self._more = not self._more
        it = self.t._item()
        if it is not None and self._finer:
            self.finer_model.update(rows.evaluate(self._finer, it, self.b.facts_of(it), self._more))
        self.changed.emit()

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
