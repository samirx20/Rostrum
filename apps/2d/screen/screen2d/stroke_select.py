"""Select, move, copy and delete strokes while Draw is on (UX_SPEC.md §3.8, "Select and move paint"): Ctrl+drag a lasso
(or Select strokes in the context bar, then drag) around strokes of what the pen paints on; drag moves them; Delete,
Copy and Paste in the bar (stroke_clip.py); the box's corner handles scale them and the knob above it turns them
(stroke_handles.py); Esc clears. Each change is one undo step through the painting kit's operations
(`stroke.set {points}`, `stroke.remove`, `paint.stroke`): the very calls an agent makes with a stroke's id.

The selection is screen state (stroke ids); points are shown in composition px through the layer's own place
(rostrum2d/placement.py, the pen's mapping), so the outline sits where the paint is on screen. A QObject part, read in
QML as `backend.strokeSelect`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication
from rostrum2d import placement
from rostrum2d.drawing import frame_at
from rostrum2d.evaluate import resolve
from rostrum_gui.edits import Drag

from . import stroke_geom as G
from .stroke_clip import StrokeClip
from .stroke_handles import StrokeHandles


class StrokeSelect(StrokeClip, StrokeHandles, QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        self._armed, self._ids, self._lasso, self._drag = False, [], [], None
        self._layer, self._place, self._comp, self._start, self._size0 = "", None, {}, {}, {}
        QGuiApplication.clipboard().dataChanged.connect(self.changed)       # Paste appears when strokes are copied
        self._at = None                                 # (selected layer, playhead) the strokes were picked at
        bridge.toolChanged.connect(self.clear)
        for s in (bridge.selectionChanged, bridge.timeChanged):     # these also fire on every document change: only a real move on counts
            s.connect(self._moved_on)
        bridge.docChanged.connect(self._doc_changed)

    def _here(self):
        return self.b.selectedLayer, self.b._t

    def _moved_on(self):
        """Another layer or another time than where the strokes were picked: let go of them."""
        if self._ids and self._here() != self._at:
            self.clear()

    # ---- reads for QML (composition px) ----------------------------------------------------------------------------
    armed = Property(bool, lambda self: self._armed, notify=changed)
    count = Property(int, lambda self: len(self._ids), notify=changed)
    ids = Property("QVariantList", lambda self: list(self._ids), notify=changed)
    canPaste = Property(bool, lambda self: bool(self._clip) and self._target() is not None, notify=changed)

    @Property(str, notify=changed)
    def lassoPath(self):
        return G.outline(self._lasso) + (" Z" if len(self._lasso) > 2 else "")

    @Property("QVariantList", notify=changed)
    def outlines(self):
        return [G.outline(self._comp[i]) for i in self._ids if i in self._comp]

    @Property("QVariantMap", notify=changed)
    def box(self):
        b = G.bounds([self._comp[i] for i in self._ids if i in self._comp])
        return {} if b is None else {"x": b[0], "y": b[1], "w": b[2] - b[0], "h": b[3] - b[1]}

    # ---- the mapping: a stroke's canvas px <-> composition px, through the layer's place ---------------------------
    def _target(self) -> dict | None:
        d = self.b.painter._aim()
        return d if d is not None and d.get("frames") else None

    def _frame(self, d: dict) -> dict | None:
        return self.b._paint_layers._frame() or frame_at(d, self.b.painter._n())

    def _sizes(self, d):
        from rostrum2d.drawing import paint_size
        return paint_size(d, resolve(d, self.b.own_t(d["id"])))

    def _to_comp(self, points: list) -> list:
        d = self.b.doc.item(self._layer)
        cw, ch = self._sizes(d)
        w, h = self._place["w"], self._place["h"]
        return [[*placement.comp_point(self._place, (p[0] + 0.5) * w / cw, (p[1] + 0.5) * h / ch), *p[2:]] for p in points]

    def _to_canvas(self, points: list) -> list:
        d = self.b.doc.item(self._layer)
        return placement.canvas_points(d, resolve(d, self.b.own_t(d["id"])), self._place, points)

    def _strokes(self, d: dict) -> list[dict]:
        f = self._frame(d)
        return [s for p in (f["paints"] if f else []) if not p.get("locked") for s in p["strokes"]]    # strokes and fills

    def _load(self):
        """Comp-px points of the picked strokes from the document now (the place is kept from when they were picked)."""
        self._ids = [i for i in self._ids if self.b.doc.has(i)]
        self._comp = {i: self._to_comp(self.b.doc.item(i)["points"]) for i in self._ids}

    def _doc_changed(self):
        if self._ids and self._drag is None:
            self._load()
            self.changed.emit()

    # ---- the lasso -------------------------------------------------------------------------------------------------
    @Slot(bool)
    def arm(self, on):
        """Select strokes in the context bar: the next drag is a lasso (without Ctrl)."""
        self._armed = on
        self.changed.emit()

    @Slot(float, float)
    def beginLasso(self, x, y):
        self.clear()
        self._lasso = [[x, y]]
        self.changed.emit()

    @Slot(float, float)
    def lassoTo(self, x, y):
        if self._lasso:
            self._lasso.append([x, y])
            self.changed.emit()

    @Slot(result=int)
    def endLasso(self):
        """The strokes inside the lasso are picked; returns how many."""
        poly, self._lasso = self._lasso, []
        n = self.select_in(poly) if len(poly) > 2 else 0
        self.changed.emit()
        return n

    def select_in(self, poly: list) -> int:
        """Pick the strokes of what the pen paints on whose points mostly lie inside the polygon (composition px)."""
        d = self._target()
        self._ids, self._comp = [], {}
        if d is None:
            return 0
        self._layer, self._place, self._at = d["id"], self.b.place_of(d["id"]), self._here()
        for s in self._strokes(d):
            pts = self._to_comp(s["points"])
            if G.picked(poly, pts):
                self._ids.append(s["id"])
                self._comp[s["id"]] = pts
        self._armed = False
        self.changed.emit()
        return len(self._ids)

    @Slot()
    def clear(self):
        if self._ids or self._lasso or self._armed:
            if self._drag is not None:
                self.endMove()
            self._ids, self._comp, self._lasso, self._armed = [], {}, [], False
            self.changed.emit()

    @Slot(float, float, result=bool)
    def hits(self, x, y):
        """Is (x, y) in the picked strokes' box (a press there moves them)?"""
        b = self.box
        return bool(b) and b["x"] <= x <= b["x"] + b["w"] and b["y"] <= y <= b["y"] + b["h"]

    # ---- changes: each is one undo step ----------------------------------------------------------------------------
    def _set_calls(self, make) -> list[dict]:
        """stroke.set calls for the picked strokes: `make(comp points)` gives the new comp points (size follows scale)."""
        calls = []
        for i in self._ids:
            pts, size = make(self._comp[i])
            args = {"points": self._to_canvas(pts)}
            item = self.b.doc.item(i)
            if size and item["type"] == "stroke":               # a fill has no brush size: its outline scales
                args["size"] = round(self._size0.get(i, item["size"]) * size, 3)
            calls.append({"op": f"{item['type']}.set", "target": [i], "args": args})
        return calls

    @Slot()
    def beginMove(self):
        if self._ids and self._drag is None:
            self.b.guard(self._begin)

    def _begin(self):
        self._place = self.b.place_of(self._layer)
        self._begin_drag("Move strokes")

    def _begin_drag(self, label):
        """A gesture from the picked strokes as they are now (their comp points and brush sizes at the press)."""
        self._drag, self._start = Drag(self.b.doc, self.b.who, label), dict(self._comp)
        self._size0 = {i: self.b.doc.item(i).get("size") for i in self._ids}

    @Slot(float, float)
    def moveBy(self, dx, dy):
        """The strokes are `dx, dy` composition px from where they were at the press."""
        if self._drag is None:
            return

        def go():
            self._comp = {i: G.moved(p, dx, dy) for i, p in self._start.items()}
            self._drag.preview(self._set_calls(lambda p: (p, 0)))
        self.b.guard(go)
        self.changed.emit()

    @Slot()
    def endMove(self):
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))
            self.changed.emit()

    def move(self, dx: float, dy: float) -> bool:
        """The picked strokes moved by dx, dy (composition px) as one change (steps, agents' screens)."""
        self.beginMove()
        self.moveBy(dx, dy)
        self.endMove()
        return bool(self._ids)

    @Slot(float, float, result=bool)
    def transform(self, scale, turn):
        """The picked strokes scaled and turned about their box's centre: one change."""
        b = self.box
        if not b:
            return False
        c, k = (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2), scale
        return self._change("Scale strokes" if turn == 0 else "Turn strokes",
                            lambda: self._set_calls(lambda p: (G.transformed(p, c, k, turn), k if k != 1 else 0)))

    @Slot(result=bool)
    def remove(self):
        return bool(self._ids) and self._change("Delete strokes", lambda: [{"op": "stroke.remove", "target": list(self._ids)}], clear=True)

    def _change(self, label, make, clear=False) -> bool:
        def go():
            calls = make()
            self.b.done(self.b.doc.apply(calls, self.b.who, label=label), "")
        ok = self.b.guard(go)
        if ok and clear:
            self.clear()
        return ok
