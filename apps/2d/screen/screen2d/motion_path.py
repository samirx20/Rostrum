"""The motion path on the canvas (backend.motionPath, MotionPath.qml): where the selected layer travels between its
position keys, one dot per frame (their spacing shows speed), a square per key, and a key's spatial handles; a jump (a
key with the `hold` ease, then the next key: for the frame, a cut) is a dashed line with no dots. For the frame, also a
faint outline of it (turned and zoomed) at each of its keys. The View menu's "Show the frame's path" (screen state, on
at first, never an undo step) keeps the frame's path and key outlines showing, faint, while something else is picked.
A layer riding a path shows none (the ride is shown). Everything is in world px, drawn through the Stage's one mapping.
The maths is motion_geo.py; the document is read once per change and selection, a playhead move only maps again, a pan
or zoom of the view costs nothing here.

Drags are one gesture = one undo step each (drags.py `_begin`): a key square moves that key's x and y (key.set v) by the
pointer's offset taken back into the layer's own px; a handle end bends the path (key.path_handles), its opposite handle
mirrored so the curve stays smooth (Alt: not mirrored). A click on a key square picks its keys (backend.keys).
Ctrl+click on the line adds a key at the time of the dot there (addKeyAt: value.set x, y {at}, motion_geo.time_near). The
frame's keys are moved the same way: the canvas is the world, so the view never moves with them.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui.after_frame import AfterFrame

from rostrum_core.keys import keys_of

from . import motion_geo as G
from rostrum2d.frame import TYPE as FRAME, view as frame_view


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
    layersChanged = Signal()           # the selected layer's path changed (layerRows)
    framesChanged = Signal()           # the frame's path changed (frameRows): the canvas draws each apart, so a layer's
                                       # drag never converts or redraws the frame's ~900 points again

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b, self._frame_path = bridge, True
        self._tracks = None            # (doc.data, selection, frame path on, [(owner id, faint, track, frame keys)])
        self._view = None              # (tracks, t, the canvas paths)
        self._by_owner = {}            # {owner id: (what it is made of, (track, frame outlines) or None)}: _track_of
        self._rows = {}                # {owner id: (what its canvas row is made of, the row)}: _row
        for sig in (bridge.timeChanged, bridge.markersChanged):
            sig.connect(self._check)
        bridge.docStepped.connect(self._doc)             # a drag's step: at once, the path follows the pointer
        self._after = AfterFrame(self._check, self)      # a change or a pick: the frame after, with the overlays
        bridge.docChanged.connect(self._after.ask)       # (outline_news.py)
        bridge.selectedItemsChanged.connect(self._after.ask)

    def _doc(self):
        """A drag's step: the canvas is told only when a path it shows is another (an edit of anything the paths are
        not made of, like a colour or an unanimated x, redraws none: the frame's path was ~900 points)."""
        if self.b.reached([o for o, _ in self._owners()]):
            self._check()

    def _check(self):
        """(After a change, whatever it touched: the changes since the frame before may be several.) Each owner's row
        is made again only when it changed (_row), so a row that is the same object shows the same: only the part
        whose rows changed is told."""
        was = self._view[2] if self._view is not None else None
        now = self.paths
        if was is None or len(now) != len(was) or any(a is not b for a, b in zip(now, was)):
            self.changed.emit()
            for frame, sig in ((False, self.layersChanged), (True, self.framesChanged)):
                if was is None or _part(was, frame) != _part(now, frame):
                    sig.emit()

    # ---- the View menu's "Show the frame's path" (screen state, never the document) -------------------------
    @Property(bool, notify=changed)
    def framePath(self) -> bool:
        return self._frame_path

    @Slot(bool)
    def setFramePath(self, on: bool):
        self._frame_path = bool(on)
        self.changed.emit()
        self._check()

    # ---- reads ------------------------------------------------------------------------------------------------
    def _owners(self) -> list[tuple[str, bool]]:
        """(id, faint) of what shows a path: the selected single layer, and the frame (faint) when the switch is on."""
        out, sel = [], self.b.selectedLayer
        if sel and len(self.b.selected_layers()) == 1 and self.b.doc.has(sel):
            out.append((sel, False))
        frame = frame_view.of(self.b.placed()) if self._frame_path else None
        if frame is not None and frame["id"] != sel:
            out.append((frame["id"], True))
        return out

    def _read(self):
        key = (id(self.b.placed()), self.b.selectedLayer, self._frame_path, self.b.placed())   # the last keeps the id alive
        if self._tracks is None or self._tracks[0][:3] != key[:3]:
            rows = []
            for oid, faint in self._owners():
                got = self._track_of(oid)
                if got is not None:
                    rows.append((oid, faint, *got))
            self._tracks = (key, rows)
        return self._tracks

    def _track_of(self, oid: str):
        """(track, frame outlines) of one owner, worked out again only when what it is made of changed: a layer's position
        (its x and y keys and values: motion_geo.track reads nothing else) and ride, the frame itself (its outlines read
        all of it), the scene's rate and size, the markers. An edit of anything else (a colour, the scale, another
        layer, the frame's other fields) reuses it (each was ~800 samples, redone on every change)."""
        c, item = self.b.comp(), self.b.placed_item(oid)        # (keys in scene seconds: a retimed layer's move too)
        own = item if item["type"] == FRAME else tuple((keys_of(item, p), item.get(p)) for p in ("x", "y")) + (item.get("ridePath"),)
        key = (own, c["fps"], c.get("width"), c.get("height"), self.b.marks.times if self.b.marks else None)
        got = self._by_owner.get(oid)
        if got is None or not all(a is b or a == b for a, b in zip(got[0], key)):
            comp, owner = self.b.placed(), self.b.placed_item(oid)
            got = self._by_owner[oid] = (key, None if owner.get("ridePath") else (
                G.track(owner, c["fps"]),
                [G.frame_at(comp, kt) for kt in G.frame_keys(owner)] if owner["type"] == FRAME else []))
        return got[1]

    @Property("QVariantList", notify=changed)
    def paths(self):
        """[{id, frame, faint, lines, cuts, ticks, keys, frames}] in world px."""
        tracks, t = self._read(), self.b._t
        if self._view is not None and self._view[0] is tracks and self._view[1] == t:
            return self._view[2]
        picked = set(self.b._keys.ids)
        out = [self._row(oid, faint, tr, frames, t, picked) for oid, faint, tr, frames in tracks[1]]
        self._view = (tracks, t, out)
        return out

    @Property("QVariantList", notify=layersChanged)
    def layerRows(self):
        """The rows of `paths` that are a layer's (the canvas draws them apart from the frame's)."""
        return [r for r in self.paths if not r["frame"]]

    @Property("QVariantList", notify=framesChanged)
    def frameRows(self):
        """The rows of `paths` that are the frame's."""
        return [r for r in self.paths if r["frame"]]

    def _row(self, oid, faint, tr, frames, t, picked):
        """One owner's canvas row, made again only when its track, outlines, mapping or picked keys changed."""
        owner = self.b.placed_item(oid)
        m = tuple(G.mapping(self.b.placed(), owner, t)) if tr else None
        mine = frozenset(i for k in tr["keys"] for i in k["ids"] if i in picked) if tr else None
        key = (tr, frames, faint, owner["type"] == FRAME, m, mine)
        got = self._rows.get(oid)
        if got is not None and all(a is b or a == b for a, b in zip(got[0], key)):
            return got[1]
        row = {"id": oid, "frame": key[3], "faint": faint, "lines": [], "cuts": [], "ticks": [], "keys": [],
               "frames": frames}
        if tr:
            row.update(G.on_canvas(tr, m))
            for k in row["keys"]:
                k["picked"] = bool(picked & set(k["ids"]))
                k["handles"] = not faint and (k["stored"] or k["picked"])
        self._rows[oid] = (key, row)
        return row

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
        """Press on a key square (composition seconds t): its keys are picked and a move starts. A layer's square at
        the playhead is where the layer is now, so the press is the layer's: it is picked (not the key) and moves, which
        writes that key all the same (else the square hid the layer's middle from a click: sweep r3 FINDINGS 9)."""
        k, m = self._key_row(oid, t)
        if k is None or self._owner_ok(oid) is None:
            return False
        if self.b.doc.item(oid)["type"] != FRAME and abs(t - self.b._t) < 0.5 / self.b.comp()["fps"]:
            self.b.select(oid) if not self.b._multi.has(oid) else self.b._keys.clear()
            return self.b.beginMove()
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
        if not self.b._begin("Bend the path", HandleGrab(oid, self.b.own_t(oid, t), side,
                                                           k[("in" if side == "out" else "out") + "Own"] is not None,
                                                           tuple(k[side + "Own"]), m)):
            return False
        return True

    @Slot(float, float, float, result=bool)
    def addKeyAt(self, x: float, y: float, limit: float) -> bool:
        """Ctrl+click on a shown path's line (canvas point x, y, world px; within `limit` world px): a position key at
        the time of the frame dot under the pointer, holding the place the path has there (After Effects), so the
        path keeps its course. One undo step, the same value.set x, y {at} an agent calls. False: no line there."""
        hit = self._line_at(x, y, limit)
        if hit is None:
            return False
        oid, owner, t = hit
        if self._owner_ok(oid) is None:
            return True
        at, (vx, vy) = self.b.own_t(oid, t), G.position(owner)(t)
        calls = [{"op": "value.set", "target": [oid], "args": {"prop": f, "at": at, "v": round(v, 2)}}
                 for f, v in (("x", vx), ("y", vy))]
        self.b.guard(lambda: self.b.done(self.b.doc.apply(calls, self.b.who, label="Add a path key"), ""))
        return True

    @Slot(float, float, float, result=bool)
    def onLine(self, x: float, y: float, limit: float) -> bool:
        """A Ctrl+click at (x, y) would add a key (addKeyAt's own test): the canvas pointer's "+" while Ctrl is held."""
        return self._line_at(x, y, limit) is not None

    def _line_at(self, x, y, limit):
        """(owner id, owner, time) of the shown path line within `limit` world px of (x, y); None: none there."""
        for p in self.paths:
            if p["faint"]:
                continue
            owner = self.b.placed_item(p["id"])
            t = G.time_near(owner, self.b.comp()["fps"], G.mapping(self.b.placed(), owner, self.b._t), x, y, limit)
            if t is not None:
                return p["id"], owner, t
        return None

    @Slot(float, float, bool)
    def drag(self, dx: float, dy: float, alt: bool):
        """The pointer's total offset from the press, composition px on the canvas; Alt: a handle's opposite stays."""
        g = self.b._grab
        if self.b._drag is not None and not isinstance(g, (KeyGrab, HandleGrab)):
            return self.b.moveBy(dx, dy)                 # the layer's own move (beginKey at the playhead)
        if self.b._drag is None:
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


def _part(rows, frame: bool) -> list[int]:
    """Which row objects of `rows` are (or are not) the frame's: the same objects show the same."""
    return [id(r) for r in rows if r["frame"] is frame]
