"""The motion path on the canvas (backend.motionPath, MotionPath.qml): where the selected layer travels between its
position keys, one dot per frame (their spacing shows speed), a square per key, and a key's spatial handles; for the
camera, its frame at the playhead and a faint one at each key. The View menu's "Camera frame" (screen state, on by
default) shows the camera's frame and path even when it isn't selected. A layer riding a path shows none (the ride is
shown). The maths is motion_geo.py; the document is read once per change and selection, a playhead move only maps again.

Drags are one gesture = one undo step each (drags.py `_begin`): a key square moves that key's x and y (key.set v) by the
pointer's offset taken back into the layer's own px; a handle end bends the path (key.path_handles), its opposite handle
mirrored so the curve stays smooth (Alt: not mirrored). A click on a key square picks its keys (backend.keys).
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import motion_geo as G
from .camera_tool import active_camera


@dataclass
class KeyGrab:
    owner: str
    ids: dict          # prop -> (key id, value at the press)
    m: tuple           # the canvas mapping at the press


@dataclass
class HandleGrab:
    owner: str
    t: float           # the key's own time
    side: str          # "out" | "in"
    mirror: bool       # the key has the opposite handle (not the first or last key)
    start: tuple       # the handle's offset at the press, own px
    m: tuple


class MotionPath(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b, self._camera_frame = bridge, True
        self._tracks = None            # (doc.data, selection, camera frame on, [(owner id, track, camera keys)])
        self._view = None              # (tracks key, t, the canvas paths)
        for sig in (bridge.docChanged, bridge.selectedItemsChanged, bridge.timeChanged, bridge.markersChanged):
            sig.connect(self.changed)

    # ---- the View menu's switch (screen state, never the document) -------------------------------------------
    @Property(bool, notify=changed)
    def cameraFrame(self) -> bool:
        return self._camera_frame

    @Slot(bool)
    def setCameraFrame(self, on: bool):
        self._camera_frame = bool(on)
        self.changed.emit()

    @Property(bool, notify=changed)
    def hasCamera(self) -> bool:
        return any(c["type"] == "camera" for c in self.b.comp().get("layers", []))

    # ---- reads ------------------------------------------------------------------------------------------------
    def _owners(self) -> list[tuple[str, bool]]:
        """(id, faint) of what shows a path: the selected single layer, and the camera when the switch is on."""
        out, sel = [], self.b.selectedLayer
        if sel and len(self.b.selected_layers()) == 1 and self.b.doc.has(sel):
            out.append((sel, False))
        cam = active_camera(self.b.placed(), self.b._t) if self._camera_frame else None
        if cam is not None and cam["id"] != sel:
            out.append((cam["id"], True))
        return out

    def _read(self):
        key = (id(self.b.placed()), self.b.selectedLayer, self._camera_frame, self.b.placed())   # the last keeps the id alive
        if self._tracks is None or self._tracks[0][:3] != key[:3]:
            fps, rows = self.b.comp()["fps"], []
            for oid, faint in self._owners():
                owner = self.b.placed_item(oid)
                if owner.get("ridePath"):
                    continue
                cam = owner["type"] == "camera"
                rows.append((oid, faint, G.track(owner, fps), G.camera_keys(owner) if cam else []))
            self._tracks = (key, rows)
        return self._tracks

    @Property("QVariantList", notify=changed)
    def paths(self):
        """[{id, camera, faint, points, ticks, keys, frames, now}] in composition px as the canvas shows them."""
        tracks = self._read()
        t = self.b._t
        if self._view is not None and self._view[0] is tracks and self._view[1] == t:
            return self._view[2]
        comp, out, picked = self.b.placed(), [], set(self.b._keys.ids)
        for oid, faint, tr, cam_keys in tracks[1]:
            owner = self.b.placed_item(oid)
            m = G.mapping(comp, owner, t)
            row = {"id": oid, "camera": owner["type"] == "camera", "faint": faint, "points": [], "ticks": [], "keys": [],
                   "frames": [], "now": []}
            if tr:
                row.update(G.on_canvas(tr, m))
                for k in row["keys"]:
                    k["picked"] = bool(picked & set(k["ids"]))
                    k["handles"] = not faint and (k["stored"] or k["picked"])
            if row["camera"]:
                row["now"] = G.frame_at(comp, owner, t, m)
                row["frames"] = [G.frame_at(comp, owner, kt, m) for kt in cam_keys if abs(kt - t) > 1e-6]
            out.append(row)
        self._view = (tracks, t, out)
        return out

    # ---- drags ------------------------------------------------------------------------------------------------
    def _owner_ok(self, oid: str) -> dict | None:
        item = self.b.doc.item(oid)
        chain, at = [item], oid
        while (up := self.b.doc.parent_of(at)[0]) and up != self.b.comp_id:
            chain.append(self.b.doc.item(up))
            at = up
        if any(i.get("locked") for i in chain):
            self.b._fail(f"Error: {item.get('name') or oid} is locked; unlock it to change its path.")
            return None
        return item

    def _key_row(self, oid: str, t: float):
        row = next((p for p in self.paths if p["id"] == oid), None)
        k = next((k for k in row["keys"] if abs(k["t"] - t) < 1e-6), None) if row else None
        return k, G.mapping(self.b.placed(), self.b.placed_item(oid), self.b._t)

    @Slot(str, float, result=bool)
    def beginKey(self, oid: str, t: float) -> bool:
        """Press on a key square (composition seconds t): its keys are picked and a move starts."""
        k, m = self._key_row(oid, t)
        if k is None or self._owner_ok(oid) is None:
            return False
        self.b._keys.click(k["ids"], "", [])
        ids = {self.b.doc.item(i)["prop"]: (i, float(self.b.doc.item(i)["v"])) for i in k["ids"]}
        if not self.b._begin("Move a path key", KeyGrab(oid, ids, m)):
            return False
        self.b._snap.begin([oid], k["pos"])           # the square snaps as a layer does (snapper.py; Ctrl or Alt: free)
        return True

    @Slot(str, float, str, result=bool)
    def beginHandle(self, oid: str, t: float, side: str) -> bool:
        k, m = self._key_row(oid, t)
        if k is None or k.get(side + "Own") is None or self._owner_ok(oid) is None:
            return False
        return self.b._begin("Bend the path", HandleGrab(oid, self.b.own_t(oid, t), side,
                                                           k[("in" if side == "out" else "out") + "Own"] is not None,
                                                           tuple(k[side + "Own"]), m))

    @Slot(float, float, bool)
    def drag(self, dx: float, dy: float, alt: bool):
        """The pointer's total offset from the press, composition px on the canvas; Alt: a handle's opposite stays."""
        g = self.b._grab
        if self.b._drag is None or not isinstance(g, (KeyGrab, HandleGrab)):
            return
        if isinstance(g, KeyGrab):
            dx, dy = self.b._snap.move(dx, dy)
        ox, oy = G.back(g.m, dx, dy)
        if isinstance(g, KeyGrab):
            moved = {"x": ox, "y": oy}
            calls = [{"op": "key.set", "target": [kid], "args": {"v": round(v + moved[p], 2)}}
                     for p, (kid, v) in g.ids.items() if p in moved]
        else:
            d = [round(g.start[0] + ox, 2), round(g.start[1] + oy, 2)]
            args = {"t": g.t, g.side: d}
            if g.mirror and not alt:
                args["in" if g.side == "out" else "out"] = [-d[0], -d[1]]
            calls = [{"op": "key.path_handles", "target": [g.owner], "args": args}]
        self.b._guard(lambda: self.b._drag.preview(calls))
