"""The bone overlay of the rig in hand (UX_SPEC 3.23; `backend.rig`, qml/BoneOverlay.qml): while a rig, or a bone,
IK chain or layer inside one, is selected with the Move tool, its posed bones and joints lie over the canvas, from the
engine that draws it (the engine's `bones` and `place` answers: one pose for the canvas, the export and this). Screen
state; every change goes through rig_drag.py's operations. Bones and joints are in composition px.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from .rig_drag import RigDrag

NEAR = 0.75                       # comp px: joints this close are one circle


def rig_around(doc, ids: list[str]) -> str:
    """The rig the selection is in or is: the first selected item that is a rig or sits inside one ("" = none)."""
    for i in ids:                           # the document's own index (kept per state), never a new one per ask
        cur = i
        while cur is not None and doc.has(cur):
            if doc.item(cur).get("type") == "rig":
                return cur
            cur = doc.parent_of(cur)[0]
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
    setsChanged = Signal()                            # the bones or joints there are changed (not where they are): QML's delegates follow this
    _answer = Signal(object, object, object)          # (key, answer, error) from the engine's thread

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._rig, self._posed, self._place, self._key, self._picked = bridge, "", {}, None, None, ""
        self._drag = RigDrag(self)
        self._answer.connect(self._got)
        self._ids, self._keys = [], []
        self.changed.connect(self._sets)
        for s in (bridge.selectedItemsChanged, bridge.docChanged, bridge.timeChanged, bridge.toolChanged, bridge.frameChanged):
            s.connect(self.refresh)

    # ---- what QML reads --------------------------------------------------------------------------------------
    @property
    def drag(self) -> RigDrag:
        return self._drag

    @Property(QObject, constant=True)
    def dragger(self):
        """The overlay's drags (rig_drag.py): QML calls `rig.dragger.beginPose(…)` (a plain attribute is not seen from QML)."""
        return self._drag

    @Property(str, notify=changed)
    def rig(self):
        """The rig in hand ("" = no overlay)."""
        return self._rig

    @Property("QVariantList", notify=setsChanged)
    def boneIds(self):
        """The ids of the bones drawn. The overlay keeps one delegate per id, so a bone being dragged is not rebuilt
        under the pointer each time the engine answers a new pose (its release never came: the drag stayed open)."""
        return self._ids

    @Property("QVariantList", notify=setsChanged)
    def jointKeys(self):
        """"bone|end" of each joint circle: the same, for the joints."""
        return self._keys

    def _sets(self):
        ids = [b["id"] for b in self.bones]
        keys = [f'{j["bone"]}|{j["end"]}' for j in self.joints]
        if ids != self._ids or keys != self._keys:
            self._ids, self._keys = ids, keys
            self.setsChanged.emit()

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
        rig = rig_around(doc, list(self.b._kit.selection)) if self.b.tool in ("move", "bone") else ""
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
            self._key = None                                 # asked again at the next frame (frameChanged -> refresh)
            if "is not drawn at this time" in str(error):    # Make rig asks before the rig's first frame has landed: no error, ask again
                return
            name = self.b.doc.item(self._rig).get("name", "") if self.b.doc.has(self._rig) else ""
            return self.b._fail(f"Error: bones: {str(error).replace(self._rig, name or 'the rig')}")   # never an internal id
        rigs, places = answer
        self._posed = rigs.get(self._rig, {}).get("bones", {})
        self._place = places.get(self._rig)
        self.changed.emit()

    @Slot(str)
    @Slot(str, bool)
    def pickBone(self, bone, add=False):
        """A click on a bone: it is picked (its settings show; the overlay stays, the rig is still in hand). Ctrl+click
        (`add`): it joins the parts selected, in place of any other bone (a part + a bone: Attach to bone, rig_attach.py)."""
        self._picked = bone
        if add:
            doc = self.b.doc
            self.b.selectMany([i for i in self.b._kit.selection if doc.has(i) and doc.item(i)["type"] != "bone"] + [bone])
        else:
            self.b.select(bone)
        self.changed.emit()
