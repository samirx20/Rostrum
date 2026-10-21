"""Rostrum2D's document bridge: the kit's DocBridge plus time, pages (design, draw, animate), the layer tree, the
canvas frame and the two drags (move a layer on the canvas, move a key on the timeline). Every change is an operation; each drag is
one doc.gesture = one undo step. How an edit becomes a call lives in route.py only.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core.keys import keys_of
from rostrum2d.evaluate import resolve
from rostrum_gui import DocBridge
from rostrum_gui.edits import Drag
from rostrum_gui.markers import MarkerWatch

from . import bounds, exprs, outline, route
from .curves import Curves
from .frames import FrameRenderer
from .painter import Painter
from .pen import Pen


class Bridge2D(DocBridge):
    timeChanged = Signal()
    pageChanged = Signal()
    frameChanged = Signal()
    outlineChanged = Signal()
    playingChanged = Signal()
    markersChanged = Signal()

    def __init__(self, doc, comp_id=None, autosave=False, parent=None):
        comps = doc.data.get("comps", [])
        if not comps:
            raise ValueError("the document has no composition yet (comp.add)")
        self.comp_id = comp_id or comps[0]["id"]
        self._t, self._page, self._frame, self.autosave = 0.0, "design", 0, autosave
        self._folded, self._opened, self._drag, self._grab = set(), set(), None, None
        super().__init__(doc, parent=parent)
        self.frames = FrameRenderer(self)
        self.frames.ready.connect(self._on_frame)
        self.frames.failed.connect(self._fail)
        self.painter = Painter(self)
        self._pen = Pen(self)
        self._curves = Curves(self)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.marks = MarkerWatch(doc.folder, self)          # the project's shared markers: ruler flags, snapping
        self.marks.changed.connect(self.markersChanged)
        self.marks.changed.connect(self._render)            # expressions may read marker("…")
        self.selectionChanged.connect(self.outlineChanged)
        self._render()

    # ---- reads for QML ----------------------------------------------------------------------------------------
    def comp(self) -> dict:
        return self.doc.item(self.comp_id)

    @Property(QObject, constant=True)
    def pen(self):
        """The pen tool and path point editing (pen.py)."""
        return self._pen

    @Property(QObject, constant=True)
    def curves(self):
        """The timeline's curve editor (curves.py)."""
        return self._curves

    @Property(float, notify=timeChanged)
    def time(self):
        return self._t

    @Property("QVariantMap", notify=outlineChanged)
    def frameInfo(self):
        c = self.comp()
        return {"width": c["width"], "height": c["height"], "fps": c["fps"], "duration": c["duration"],
                "label": outline.label_of(c)}

    @Property(str, notify=pageChanged)
    def page(self):
        return self._page

    @Property(bool, notify=playingChanged)
    def playing(self):
        return self._timer.isActive()

    @Property(int, notify=frameChanged)
    def frame(self):
        return self._frame

    @Property("QVariantList", notify=markersChanged)
    def markers(self):
        return self.marks.rows()

    @Property("QVariantList", notify=outlineChanged)
    def layers(self):
        return outline.layer_rows(self.comp(), self._folded)

    @Property("QVariantList", notify=outlineChanged)
    def tracks(self):
        return outline.tracks(self.comp(), self._opened)

    @Property(str, notify=outlineChanged)
    def selectedLayer(self):
        """The layer the selection belongs to (itself, or the layer of a selected effect, mask or key)."""
        return bounds.layer_of(self.doc, self._sel) if self._sel else ""

    @Property("QVariantMap", notify=outlineChanged)
    def selBox(self):
        layer = self.selectedLayer
        return next((b for b in bounds.boxes(self.comp(), self._t) if b["id"] == layer), {})

    # ---- the kit's hooks: the 2D animation model (route.py) ---------------------------------------------------
    def label_of(self, item):
        owner = self.doc.item(self.doc.parent_of(item["id"])[0]) if item.get("type") == "key" else None
        return outline.label_of(item, owner)

    def edit_call(self, item_id, param, value):
        return route.edit_call(self.doc, item_id, param, value, self._t)

    def shown_values(self, item):
        return route.shown_values(item, self._t)

    def anim_state(self, item, param):
        return route.anim_state(item, param, self._t, self.comp()["fps"])

    def animate_calls(self, item_id, param):
        return route.animate_calls(self.doc.item(item_id), param, self._t)

    def expr_state(self, item, param):
        return exprs.state(item, param)

    def clear_expr_calls(self, item_id, param):
        return exprs.clear_calls(self.doc.item(item_id), param)

    def _first(self):
        rows = outline.layer_rows(self.comp(), set())
        return rows[0]["id"] if rows else self.comp_id

    # ---- screen state -----------------------------------------------------------------------------------------
    @Slot(float)
    def setTime(self, t):
        c = self.comp()
        self._t = min(max(round(t * c["fps"]) / c["fps"], 0.0), c["duration"])
        self.model.update(self._rows())
        self.timeChanged.emit()
        self.outlineChanged.emit()
        self._render()

    @Slot(str)
    def setPage(self, page):
        self._page = page
        self.pageChanged.emit()

    @Slot()
    def togglePlay(self):
        if self._timer.isActive():
            self._timer.stop()
        else:
            self._timer.start(round(1000 / self.comp()["fps"]))
        self.playingChanged.emit()

    @Slot(str)
    def toggleFold(self, item_id):
        self._folded ^= {item_id}
        self.outlineChanged.emit()

    @Slot(str)
    def toggleTrack(self, item_id):
        self._opened ^= {item_id}
        self.outlineChanged.emit()

    @Slot(float, float, result=str)
    def pickAt(self, x, y):
        """A click on the canvas (composition px): select the topmost layer there; on empty canvas, the
        composition (its frame size, rate, length, background)."""
        hit = bounds.pick(self.comp(), self._t, x, y)
        if hit != self.selectedLayer:
            self.select(hit or self.comp_id)
        return hit

    # ---- drags: each one doc.gesture = one change --------------------------------------------------------------
    @Slot(result=bool)
    def beginMove(self):
        layer = bounds.layer_of(self.doc, self._sel) if self._sel else ""
        if not layer:
            return False
        if any(exprs.drives(self.doc.item(layer), a) for a in ("x", "y")):
            self._fail("Error: move: x or y is driven by an expression; clear it first (the cross on its row).")
            return False
        p = resolve(self.doc.item(layer), self._t)
        return self._begin(f"Move {self.label_of(self.doc.item(layer))}", (layer, p["x"], p["y"]))

    @Slot(float, float)
    def moveBy(self, dx, dy):
        """Total offset from where the drag started, in composition px: value.set x / y at the playhead."""
        if self._drag is None or self._grab is None:
            return
        layer, x0, y0 = self._grab
        item = self.doc.item(layer)
        self._guard(lambda: self._drag.preview([route.value_call(item, "x", round(x0 + dx, 2), self._t),
                                                route.value_call(item, "y", round(y0 + dy, 2), self._t)]))

    @Slot(str, result=bool)
    def beginKeyDrag(self, key_id):
        self.select(key_id)
        return self._begin("Move key", key_id)

    @Slot(float, float)
    def keyDragTo(self, t, snap=0.0):
        """`snap`: seconds within which the key lands on a shared marker instead of the nearest frame."""
        if self._drag is None or not isinstance(self._grab, str):
            return
        c, key = self.comp(), self.doc.item(self._grab)
        on = self.marks.snap(t, snap)
        t = min(max(on if on != t else round(t * c["fps"]) / c["fps"], 0.0), c["duration"])
        owner = self.doc.item(self.doc.parent_of(key["id"])[0])
        if any(k["id"] != key["id"] and abs(k["t"] - t) < 1e-6 for k in keys_of(owner, key["prop"])):
            return                       # another key of this field is there: stay at the last free time
        self._guard(lambda: self._drag.preview([{"op": "key.set", "target": [key["id"]], "args": {"t": t}}]))

    @Slot()
    def endDrag(self):
        d, self._drag, self._grab = self._drag, None, None
        if d is not None:
            self._guard(lambda: self._done(d.end(), ""))

    def _begin(self, label, grab) -> bool:
        self.endDrag()

        def go():
            self._drag, self._grab = Drag(self.doc, self.who, label), grab
        return self._guard(go)

    # ---- for the Painter (screen2d/painter.py) ----------------------------------------------------------------
    def guard(self, fn) -> bool:
        return self._guard(fn)

    def done(self, change, nothing):
        self._done(change, nothing)

    # ---- inside -----------------------------------------------------------------------------------------------
    def _tick(self):
        c = self.comp()
        nxt = self._t + 1 / c["fps"]
        self.setTime(0.0 if nxt > c["duration"] + 1e-9 else nxt)

    def _render(self):
        from rostrum2d.scene import describe
        self.frames.request(describe(self.doc.data, self.comp_id, self.marks.times), self._t)

    def _on_frame(self, serial):
        self._frame = serial
        self.frameChanged.emit()

    def _on_doc(self, event):
        super()._on_doc(event)
        self.outlineChanged.emit()
        self._render()
        if self.autosave and event.kind == "change":
            self._guard(self.doc.save)

    def close(self):
        self._timer.stop()
        self.marks.close()
        self.endDrag()
        self.frames.close()
