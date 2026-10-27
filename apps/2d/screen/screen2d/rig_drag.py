"""Drags on the bone overlay (UX_SPEC 3.23; `backend.rig.drag`, qml/BoneOverlay.qml). Each press-drag-release is one
gesture = one undo step, made of the operations an agent calls:

- a joint circle: fixes the joint at rest (`rig.move_joint`);
- a bone in an IK chain (its bones, or a hand / foot hanging from its lower bone): pulls the chain's target with the
  pointer (`key.add` targetX / targetY at the playhead);
- any other bone: turns it about its joint (`key.add` rotation at the playhead: FK);
- right-click a chain's end › Pin / Unpin (`ik.pin`, a hold key at the playhead).
A pose is keyed at the playhead, always (a pose drag that only changed a still value moved every frame at once and left
no keys: 2D final critic row 3). The same pose drags start from a press on a bound part (rig_view.pressAt, Stage.qml).
Pointer points are composition px; they go to the rig's own px through the engine's `place` (placement.own_point).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QObject, Signal, Slot
from rostrum2d.evaluate import value_at
from rostrum2d.placement import own_point
from rostrum_gui.edits import Drag


def chain_bones(rig: dict, ik: dict) -> list[str]:
    """The bones an IK chain moves: `chain` bones from its lower bone up, and the bones hanging from the lower bone."""
    up = {b["id"]: b["parent"] for b in rig.get("bones", [])}
    out, cur = [], ik["bone"]
    for _ in range(int(ik.get("chain", 2))):
        if not cur:
            break
        out.append(cur)
        cur = up.get(cur, "")
    return out + [b for b, p in up.items() if p == ik["bone"]]


SHORT = "Not posed: the drag was too short to move the part (a click only picks its bone). Drag a little further."


class RigDrag(QObject):
    changed = Signal()

    def __init__(self, view):
        super().__init__(view)
        self.v, self._drag, self._how = view, None, None

    @property
    def b(self):
        return self.v.b

    def chain_of(self, rig: dict, bone: str) -> str:
        """The IK chain a drag on this bone pulls ("" = it turns by itself)."""
        return next((k["id"] for k in rig.get("iks", []) if k.get("mode", "ik") == "ik" and bone in chain_bones(rig, k)), "")

    def pinned(self, ik: str) -> bool:
        item = self.b.doc.item(ik)
        return value_at(item, "pin", self.b.own_t(ik)) >= 0.5

    def _own(self, x, y):
        place = self.v.place()
        if place is None:
            raise ValueError("the rig's place is not known yet")
        return own_point(place, x, y)

    def _open(self, label) -> bool:
        def go():
            self._drag = Drag(self.b.doc, self.b.who, label)
        if self._drag is not None:
            self.end()
        return self.b.guard(go)

    # ---- the drags -------------------------------------------------------------------------------------------
    @Slot(str, str, result=bool)
    def beginJoint(self, bone, end):
        """Press on a joint circle: fixing it starts (end = "pivot" or "tip")."""
        self._how = ("joint", bone, end)
        return self._open(f"Move joint of {self.b.doc.item(bone)['name']}")

    @Slot(str, float, float, result=bool)
    def beginPose(self, bone, x, y):
        """Press on a bone at (x, y): an IK pull when it is in a chain, else a turn about its joint."""
        rig = self.b.doc.item(self.v.rig)
        ik, p0 = self.chain_of(rig, bone), self._own(x, y)
        if ik:
            item, t = self.b.doc.item(ik), self.b.own_t(ik)
            self._how = ("ik", ik, t, p0, (value_at(item, "targetX", t), value_at(item, "targetY", t)))
            return self._open(f"Pose {item['name']}")
        posed = next((p for p in self.v.bones if p["id"] == bone), None)
        if posed is None:
            return False
        item, t = self.b.doc.item(bone), self.b.own_t(bone)
        pivot = self._own(posed["x"], posed["y"])
        self._how = ("fk", bone, t, pivot, math.atan2(p0[1] - pivot[1], p0[0] - pivot[0]), value_at(item, "rotation", t))
        return self._open(f"Turn {item['name']}")

    @Slot(float, float)
    def moveTo(self, x, y):
        """The pointer at (x, y) composition px: the drag's calls, previewed (one change at the end)."""
        if self._drag is None:
            return
        p, how = self._own(x, y), self._how
        if how[0] == "joint":
            calls = [{"op": "rig.move_joint", "target": [how[1]],
                      "args": {"x": round(p[0], 2), "y": round(p[1], 2), "end": how[2]}}]
        elif how[0] == "ik":
            _, ik, t, p0, (tx, ty) = how
            calls = [{"op": "key.add", "target": [ik], "args": {"prop": f, "t": t, "v": round(v, 2)}}
                     for f, v in (("targetX", tx + p[0] - p0[0]), ("targetY", ty + p[1] - p0[1]))]
        else:
            _, bone, t, pivot, a0, r0 = how
            turn = math.degrees(math.atan2(p[1] - pivot[1], p[0] - pivot[0]) - a0)
            turn = (turn + 180) % 360 - 180
            calls = [{"op": "key.add", "target": [bone], "args": {"prop": "rotation", "t": t, "v": round(r0 + turn, 2)}}]
        self.b.guard(lambda: self._drag.preview(calls))

    @Slot()
    def end(self):
        """Let go: one change. A drag too short to change the pose says so on the status line (hand maker C, C11: an
        8 px drag left no key and no word)."""
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), SHORT))

    @Slot()
    def short(self):
        """A press that moved a little but less than a drag: it only picks the bone; the status line says so."""
        self.cancel()
        self.b._set_status(SHORT, False)

    @Slot()
    def cancel(self):
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: d.end(cancel=True))

    @Slot(str, bool)
    def pin(self, ik, on):
        """Right-click a chain's end › Pin / Unpin: a hold key on the chain's pin at the playhead (one change)."""
        call = {"op": "ik.pin", "target": [ik], "args": {"t": round(self.b.own_t(ik), 6), "on": bool(on)}}
        self.b.guard(lambda: self.b._apply([call], "Pin" if on else "Unpin"))
