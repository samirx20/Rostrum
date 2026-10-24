"""Select, move, copy and delete strokes while Draw is on (UX_SPEC.md §3.8, "Select and move paint"): Ctrl+drag a lasso
(or Select strokes in the context bar, then drag) around strokes of what the pen paints on; drag moves them; Delete,
Copy and Paste in the bar (stroke_clip.py); the box's corner handles scale them and the knob above it turns them
(stroke_handles.py); Esc clears. Each change is one undo step through the painting kit's operations
(`stroke.transform`, `stroke.remove`, `paint.stroke`): the very calls an agent makes with a stroke's id. A drag previews
`stroke.set {points}` from where the strokes were at the press; its one recorded step is the `stroke.transform` the drag
came to (`_xf`), so a dragged move and an agent's typed one leave the same step.

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
from .stroke_through import Through


MIN_BOX = 16.0              # composition px: the picked strokes' box is at least this thick, so a press can hit a straight line


class StrokeSelect(StrokeClip, StrokeHandles, QObject):
    changed = Signal()
    knobChanged = Signal()                              # its own: QML sets it from the box, which `changed` moves

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        self._armed, self._ids, self._lasso, self._drag = False, [], [], None
        self._layer, self._place, self._comp, self._start, self._size0 = "", None, {}, {}, {}
        self._thru = None                               # a painted fill painted in place: its mapping (stroke_through.py)
        self._xf = {}                                   # the drag so far as stroke.transform's numbers
        self._knob_below = False                        # the turn knob under the box (StrokeOverlay.qml: the bar covers above)
        QGuiApplication.clipboard().dataChanged.connect(self.changed)       # Paste appears when strokes are copied
        self._at = None                                 # (selected layer, playhead) the strokes were picked at
        bridge.toolChanged.connect(self.clear)
        for s in (bridge.selectedItemsChanged, bridge.timeChanged):     # only a real move on counts (the same layer and time keep them)
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
    def _set_knob_below(self, on):
        if on != self._knob_below:
            self._knob_below = on
            self.knobChanged.emit()
    knobBelow = Property(bool, lambda self: self._knob_below, _set_knob_below, notify=knobChanged)
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
        if b is None:
            return {}
        px, py = max(0.0, (MIN_BOX - (b[2] - b[0])) / 2), max(0.0, (MIN_BOX - (b[3] - b[1])) / 2)   # a straight stroke has a box too
        return {"x": b[0] - px, "y": b[1] - py, "w": b[2] - b[0] + 2 * px, "h": b[3] - b[1] + 2 * py}

    # ---- the mapping: a stroke's canvas px <-> composition px, through the layer's place ---------------------------
    def _target(self) -> dict | None:
        """What the pen paints on, holding strokes (a painted fill painted in place: its painting)."""
        d = self.b.painter._aim()
        return d if d is not None and d.get("frames") else None

    def _seen_on(self, d: dict, at=None):
        """Where the strokes of `d` are seen: its own place, or painting a painted fill in place, the element's place
        and the fill's mapping (`at`: the lasso's middle picks the tile)."""
        through = self.b.painter.through()
        if through is None:
            self._layer, self._place, self._thru = d["id"], self.b.place_of(d["id"]), None
        else:
            self._layer, self._place = through["id"], self.b.place_of(through["id"])
            keep = (self._thru.dx, self._thru.dy) if self._thru is not None and at is None else None
            self._thru = Through(self.b, through, d, self._place, at)
            if keep is not None:
                self._thru.dx, self._thru.dy = keep

    def _frame(self, d: dict) -> dict | None:
        return self.b._paint_layers._frame() or frame_at(d, self.b.painter._n())

    def _to_comp(self, points: list) -> list:
        if self._thru is not None:
            return self._thru.to_comp(points)
        d = self.b.doc.item(self._layer)
        return placement.comp_points(d, resolve(d, self.b.own_t(d["id"])), self._place, points)

    def _to_canvas(self, points: list) -> list:
        if self._thru is not None:
            return self._thru.to_canvas(points)
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
        self._seen_on(d, (sum(q[0] for q in poly) / len(poly), sum(q[1] for q in poly) / len(poly)) if poly else None)
        self._at = self._here()
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
        self._seen_on(self._target())
        self._begin_drag("Move strokes")

    def _begin_drag(self, label):
        """A gesture from the picked strokes as they are now (their comp points and brush sizes at the press)."""
        self._drag, self._start, self._label, self._xf = Drag(self.b.doc, self.b.who, label), dict(self._comp), label, {}
        self._size0 = {i: self.b.doc.item(i).get("size") for i in self._ids}

    @Slot(float, float)
    def moveBy(self, dx, dy):
        """The strokes are `dx, dy` composition px from where they were at the press."""
        if self._drag is None:
            return

        def go():
            self._comp = {i: G.moved(p, dx, dy) for i, p in self._start.items()}
            self._xf = {"dx": round(dx, 2), "dy": round(dy, 2)}
            self._drag.preview(self._set_calls(lambda p: (p, 0)))
        self.b.guard(go)
        self.changed.emit()

    @Slot()
    def endMove(self):
        """Let go: the previews are put back and the drag's stroke.transform is the one step (none if it went nowhere)."""
        d, self._drag, self._size0, xf = self._drag, None, {}, self._xf
        self._xf = {}
        if d is None:
            return
        if self._thru is not None:          # through a painted fill: the strokes as previewed, in the painting's px
            self.b.guard(lambda: self.b.done(d.end(), ""))
            self.changed.emit()
            return
        d.end(cancel=True)
        if xf:
            self._change(self._label, lambda: [self._xf_call(xf)])
        self.changed.emit()

    def _xf_call(self, args: dict) -> dict:
        """stroke.transform on the picked strokes, where they are seen now (the playhead's frame)."""
        from rostrum2d.drawing import frame_number
        n = frame_number(self.b._t, self.b.comp()["fps"])
        return {"op": "stroke.transform", "target": list(self._ids), "args": {**args, "frame": n}}

    def move(self, dx: float, dy: float) -> bool:
        """The picked strokes moved by dx, dy (composition px) as one change (steps, agents' screens)."""
        self.beginMove()
        self.moveBy(dx, dy)
        self.endMove()
        return bool(self._ids)

    @Slot(float, float, result=bool)
    def transform(self, scale, turn):
        """The picked strokes scaled and turned about their box's centre: one change (stroke.transform; through a
        painted fill, their points set as seen)."""
        if self._ids and self._thru is not None:
            b = self.box
            c = (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
            self._size0 = {i: self.b.doc.item(i).get("size") for i in self._ids}
            self._comp = {i: G.transformed(p, c, scale, turn) for i, p in self._comp.items()}
            return self._change("Scale strokes" if turn == 0 else "Turn strokes",
                                lambda: self._set_calls(lambda p: (p, scale if scale != 1 else 0)))
        return bool(self._ids) and self._change("Scale strokes" if turn == 0 else "Turn strokes",
                                                lambda: [self._xf_call({"scale": scale, "turn": turn})])

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
