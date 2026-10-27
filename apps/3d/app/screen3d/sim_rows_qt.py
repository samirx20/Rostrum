"""The Scene panel's Simulation rows from the shot's own fields (brief 26a; QML's `backend.simRows`, ScenePanel.qml):
Timing (Every frame · On 2s · On 3s) and Simplify, drawn by the kit's InspectorRow from member B's field data
(rostrum3d/sim/fields.py SHOT), so a field added there shows here with its own words. Each edit is the shot's
field edit (shot.set through the bridge's edit_call): one undo step; a Simplify drag is one gesture. Neither is in the
stored result's key (they are applied when the result is read), so changing them never makes it out of date.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import rows, sections
from rostrum_gui.edits import Scrub
from rostrum_gui.model import RowsModel

from . import route

NAMES = ("simTiming", "simSimplify")


class SimRows(QObject):
    rowsChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b, self._scrub, self._shot = bridge, None, ""
        self.model = RowsModel(rows.ROLES, self)
        bridge.outlineChanged.connect(self._rows)
        self._rows()

    rows = Property(QObject, lambda self: self.model, constant=True)

    def _rows(self):
        b = self.b
        shot = next((s for s in b.doc.data.get("shots", []) if s["id"] == b.shot_id), None)
        op = b.doc.kind.registry.field_op("shot")
        if shot is None or op is None:
            self.model.reset([])
            return self.rowsChanged.emit()
        static = [{**r, "members": [m for m in r["members"] if m in NAMES]} if r.get("fold") == "Simulation" else r
                  for r in sections.layout(op, "shot") if r.get("id") in NAMES or r.get("fold") == "Simulation"]
        out = rows.evaluate(static, route.shown_values(shot, b.time), b.facts_of(shot), False,
                            opened={"Simulation": True})            # their fold: open (the panel titles it)
        out = [r for r in out if r.get("id") in NAMES]               # the rows only: the Scene panel has its own title
        self.model.reset(out) if shot["id"] != self._shot or len(out) != len(self.model.rows) else self.model.update(out)
        self._shot = shot["id"]
        self.rowsChanged.emit()

    # ---- InspectorRow's bridge -----------------------------------------------------------------------------------
    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        b = self.b
        return b._guard(lambda: b._done(b.doc.apply([b.edit_call(b.shot_id, param, value)], b.who,
                                                    label=f"Simulation: {param}"), ""))

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()
        b = self.b
        b._guard(lambda: setattr(self, "_scrub", Scrub(b.doc, b.who, [b.shot_id], param, b.edit_call)))

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if self._scrub is None or self._scrub.name != param:
            self.beginScrub(param)
        if self._scrub is not None:
            self.b._guard(lambda: self._scrub.preview(value))

    @Slot()
    def endScrub(self):
        s, self._scrub = self._scrub, None
        if s is not None:
            self.b._guard(lambda: self.b._done(s.end(), ""))

    @Slot()
    def cancelScrub(self):
        s, self._scrub = self._scrub, None
        if s is not None:
            self.b._guard(lambda: self.b._done(s.end(True), ""))

    @Slot(str)
    def toggleGroup(self, group):
        pass                                            # the rows sit under the Scene panel's own Simulation title

    @Slot(str)
    def toggleAnimate(self, param):
        self.b.fail_line("Error: Timing and Simplify are not keyed: they apply to the whole stored result.")
