"""The bone overlay of the rig in hand (UX_SPEC 3.23; `backend.rig`, qml/BoneOverlay.qml): while a rig, or a bone,
IK chain or layer inside one, is selected with the Move tool, its posed bones and joints lie over the canvas, from the
engine that draws it (the engine's `bones` and `place` answers: one pose for the canvas, the export and this). Screen
state; every change goes through rig_drag.py's operations. Bones and joints are in composition px.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.tree import index

from .rig_drag import RigDrag

NEAR = 0.75                       # comp px: joints this close are one circle


def rig_around(doc, ids: list[str]) -> str:
    """The rig the selection is in or is: the first selected item that is a rig or sits inside one ("" = none)."""
    idx = index(doc.data, doc.kind.lists)
    for i in ids:
        cur = i
        while cur in idx:
            if idx[cur].item.get("type") == "rig":
                return cur
            cur = idx[cur].parent
    return ""


def joints_of(rig: dict, posed: dict) -> list[dict]:
    """One circle per joint: each bone's pivot (moving it fixes that joint), and the tip of a bone with no children (the
    end of a hand or foot). `ik`: the chain whose end it is (right-click › Pin)."""
    bones = rig.get("bones", [])
    kids = {b["parent"] for b in bones}
    ends = {k["bone"]: k["id"] for k in rig.get("iks", []) if k.get("mode", "ik") == "ik"}
    out = []

    def add(x, y, bone, end, ik):
        if all(abs(j["x"] - x) + abs(j["y"] - y) > NEAR for j in out):
            out.append({"x": x, "y": y, "bone": bone, "end": end, "ik": ik})
        elif ik:
            next(j for j in out if abs(j["x"] - x) + abs(j["y"] - y) <= NEAR)["ik"] = ik
    for b in bones:
        p = posed.get(b["id"])
        if p:
            add(p["x"], p["y"], b["id"], "pivot", ends.get(b["parent"], ""))
            if b["id"] not in kids:
                add(p["tipX"], p["tipY"], b["id"], "tip", ends.get(b["id"], ""))
    return out


class RigView(QObject):
    changed = Signal()
    _answer = Signal(object, object, object)          # (key, answer, error) from the engine's thread

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._rig, self._posed, self._place, self._key, self._picked = bridge, "", {}, None, None, ""
        self.drag = RigDrag(self)
        self._answer.connect(self._got)
        for s in (bridge.selectionChanged, bridge.docChanged, bridge.timeChanged, bridge.toolChanged, bridge.frameChanged):
            s.connect(self.refresh)

    # ---- what QML reads --------------------------------------------------------------------------------------
    @Property(str, notify=changed)
    def rig(self):
        """The rig in hand ("" = no overlay)."""
        return self._rig

    @Property("QVariantList", notify=changed)
    def bones(self):
        """{id, name, x, y, tipX, tipY, picked, chain}: posed, comp px; `chain` = the IK chain a drag on it pulls."""
        if not self._rig:
            return []
        rig, out = self.b.doc.item(self._rig), []
        for b in rig.get("bones", []):
            p = self._posed.get(b["id"])
            if p:
                out.append({"id": b["id"], "name": b["name"], "x": p["x"], "y": p["y"], "tipX": p["tipX"],
                            "tipY": p["tipY"], "picked": b["id"] == self._picked, "chain": self.drag.chain_of(rig, b["id"])})
        return out

    @Property("QVariantList", notify=changed)
    def joints(self):
        """{x, y, bone, end, ik, pinned}: the circles a drag fixes (rest); `ik` set where right-click offers Pin."""
        if not self._rig:
            return []
        rig = self.b.doc.item(self._rig)
        out = joints_of(rig, self._posed)
        for j in out:
            j["pinned"] = bool(j["ik"]) and self.drag.pinned(j["ik"])
        return out

    # ---- the engine's answer ---------------------------------------------------------------------------------
    def place(self):
        """The rig's own px <-> comp px mapping at the playhead (the engine's `place`), or None before the first answer."""
        return self._place

    @Slot()
    def refresh(self):
        doc = self.b.doc
        rig = rig_around(doc, list(self.b._kit.selection)) if self.b.tool == "move" else ""
        if rig != self._rig:
            self._rig, self._posed, self._place = rig, {}, None
            self._picked = self._picked if rig else ""
            self.changed.emit()
        scene = self.b._scene
        if not rig or not scene:
            return
        key = (id(scene), self.b.time, rig)
        if key == self._key:
            return
        self._key = key
        t = self.b.time

        def ask(eng):
            return eng.bones(t), eng.place(t, [rig])
        self.b.frames.ask(scene, ask, lambda a, e: self._answer.emit(key, a, e))

    def _got(self, key, answer, error):
        if key != self._key:
            return                                       # an older question: the newest wins
        if error is not None:
            self._key = None
            return self.b._fail(f"Error: bones: {error}")
        rigs, places = answer
        self._posed = rigs.get(self._rig, {}).get("bones", {})
        self._place = places.get(self._rig)
        self.changed.emit()

    @Slot(str)
    def pickBone(self, bone):
        """A click on a bone: it is picked (its settings show; the overlay stays, the rig is still in hand)."""
        self._picked = bone
        self.b.select(bone)
        self.changed.emit()
