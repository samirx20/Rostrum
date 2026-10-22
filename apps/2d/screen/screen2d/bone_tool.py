"""The Bone tool (J; UX_SPEC 3.23; `backend.boneTool`, qml/BoneTool.qml): draw a rig's bones by hand.

Press at a joint and drag to where the bone ends, or click joint after joint: each bone is one `bone.draw` (rig/draw.py,
the agents' operation too) = one undo step, and the next one starts at its tip, hanging from it (a chain). Pressing on a
joint the rig already has starts there (a branch: an arm from the shoulder). Esc ends the chain; Esc again goes back to
Move. The tool is there only while a rig is in hand (selected, or a part or bone inside one): rule of individuality.

Points arrive in composition px and go to the rig's own px through the engine's `place` (rig_view.py), the mapping its
bone overlay uses. Bones are drawn at rest, so an existing joint is picked where it shows (posed) and used where it is
at rest.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d.placement import comp_point, own_point

from .rig_view import rig_around


class BoneTool(QObject):
    changed = Signal()

    def __init__(self, bridge, rig_view, parent=None):
        super().__init__(parent or bridge)
        self.b, self.v = bridge, rig_view
        self._from = None                   # (rig px point, parent bone id or None = found from the joint): the chain
        self._press = None                  # (comp px point, the start it makes, on a joint) while the button is down
        self._pointer = None
        for sig in (bridge.selectionChanged, bridge.docChanged):
            sig.connect(self._check)
        rig_view.changed.connect(self.changed)

    # ---- what QML reads --------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def available(self) -> bool:
        """A rig is in hand: only then is the tool offered."""
        return bool(rig_around(self.b.doc, list(self.b._kit.selection)))

    @Property(bool, notify=changed)
    def drawing(self) -> bool:
        """A chain is going (Esc ends it before it leaves the tool)."""
        return self._from is not None or self._press is not None

    @Property("QVariantList", notify=changed)
    def line(self):
        """[x0, y0, x1, y1] comp px: the bone the pointer would make now ([] = none)."""
        start = self._press[1] if self._press else self._from
        if start is None or self._pointer is None or self.v.place() is None:
            return []
        return [*comp_point(self.v.place(), *start[0]), *self._pointer]

    # ---- input -----------------------------------------------------------------------------------------------
    def _own(self, x, y):
        place = self.v.place()
        if place is None:
            raise ValueError("the rig's place is not known yet")
        return own_point(place, x, y)

    def _joint_at(self, x, y, near):
        """(rest point, parent) of the joint shown within `near` comp px of (x, y), else None."""
        j = min(self.v.joints, key=lambda j: math.dist((j["x"], j["y"]), (x, y)), default=None)
        if j is None or math.dist((j["x"], j["y"]), (x, y)) > near:
            return None
        bone = self.b.doc.item(j["bone"])
        if j["end"] == "tip":
            a = math.radians(bone["angle"])
            return (bone["x"] + bone["length"] * math.cos(a), bone["y"] + bone["length"] * math.sin(a)), bone["id"]
        return (bone["x"], bone["y"]), bone["parent"]

    @Slot(float, float, float, result=bool)
    def press(self, x, y, near):
        """The button goes down at (x, y) comp px; `near` = how far (comp px) a joint is caught from."""
        def go():
            joint = self._joint_at(x, y, near)
            self._press, self._pointer = ((x, y), joint or (self._own(x, y), None), joint is not None), (x, y)
        ok = self.b.guard(go)
        self.changed.emit()
        return ok

    @Slot(float, float)
    def hover(self, x, y):
        self._pointer = (x, y)
        if self.drawing:
            self.changed.emit()

    @Slot(float, float, float)
    def release(self, x, y, near):
        """The button comes up: a drag draws from where it was pressed; a click draws from the chain's end (or, with no
        chain yet, only marks where the first joint is)."""
        if self._press is None:
            return
        (px, py), here, on_joint = self._press
        self._press = None
        if math.dist((px, py), (x, y)) > near:              # a drag: a bone from the press to here
            self._draw(here, x, y)
        elif self._from is None or on_joint:                 # a click starting (or branching) a chain
            self._from = here
        else:                                                # a click going on: a bone from the chain's end
            self._draw(self._from, x, y)
        self.changed.emit()

    def _draw(self, start, x, y):
        rig = rig_around(self.b.doc, list(self.b._kit.selection))
        (sx, sy), parent = start

        def go():
            tx, ty = self._own(x, y)
            args = {"x": round(sx, 2), "y": round(sy, 2), "tipX": round(tx, 2), "tipY": round(ty, 2)}
            if parent:                                  # a joint at a root's start: found again from the joint (a root)
                args["parent"] = parent
            self.b.done(self.b.doc.apply([{"op": "bone.draw", "target": [rig], "args": args}], self.b.who,
                                         label="Draw bone"), "")
            new = self.b.doc.item(rig)["bones"][-1]
            self._from = ((tx, ty), new["id"])
        if not self.b.guard(go):
            self._from = None

    @Slot(result=bool)
    def end(self) -> bool:
        """Esc: the chain ends (True), or there was none (False: the caller leaves the tool)."""
        was = self.drawing
        self._from = self._press = None
        self.changed.emit()
        return was

    @Slot()
    def _check(self):
        """The rig left the selection: the chain ends and the tool goes back to Move."""
        if not self.available:
            self._from = self._press = None
            if self.b.tool == "bone":
                self.b.setTool("move")
        self.changed.emit()
