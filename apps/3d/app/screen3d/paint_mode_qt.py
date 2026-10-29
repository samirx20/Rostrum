"""Paint mode on screen, for QML as `paintMode` (SPEC §5, mockup 06). With one mesh or clay selected, Paint (B) turns
it on; a mesh with no unfolded surface is unfolded first (`mesh.unfold`, its own undo step; nothing asked); a clay's
surface is unfolded by the core for each shape by itself (clay_paint.py), so nothing waits. The settings
panel becomes Brush (paint_brush_qt.py) and Paint layers (+ new layer; each: name, what it paints, eye). A left drag
on the viewport paints on the active layer: each point is picked by the engine (its `uv`), the trail is drawn over the
picture while the drag lasts, and the release is one call list, one undo step (paint_mode.stroke_calls). Middle drag
orbits, Shift pans. B or Esc leaves; selecting something else leaves too. Where the brush lands is screen state:
On the surface (each point picked, the stroke kept on the canvas) or From the view (kept as drawn and laid on every item
it crosses when the canvas is made: paint_stroke.py); the coverage tint and its percent come from coverage_qt.py.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from . import paint_mode as P
from .coverage_qt import Coverage
from .paint_brush_qt import PaintBrush
from .paint_layer_qt import PaintLayerRows
from .paint_stroke import PaintStroke


class PaintMode(PaintStroke, QObject):
    changed = Signal()
    trailChanged = Signal()
    answered = Signal(object)            # (drag number, pick answer or error line, x, y) from the engine thread

    def __init__(self, bridge, viewport):
        super().__init__(viewport)
        self.b, self.v = bridge, viewport
        self.brush = PaintBrush(self, folder=lambda: getattr(bridge.doc, "folder", None),
                                fail=lambda line: bridge.fail_line(f"Error: {line.removeprefix('Error: ')}"))
        self.coverage = Coverage(self, viewport)
        self._on, self._id, self._active = False, "", ""
        self._drag, self._pts, self._trail, self._busy, self._next, self._up = 0, [], [], False, None, True
        self._scene = self._cam = None
        self._ratio = 1.0                # screen px per canvas px, from the last two picks (the cursor's size)
        self._anchors, self._moved, self._mpp, self._mpp_screen = [], [0.0, 0.0], None, None   # a clay's (paint_stroke)
        self._where, self._pose, self._holding = "surface", None, False     # From the view: its pose; trail held
        self._how = "stroke"                                                # Brush | Stamp (on a Relief layer)
        self._pick_dist = None                                              # a clay stamp click: metres from the eye
        self.layerRows = PaintLayerRows(self, self)             # the chosen layer's Fill and Mask rows
        self.answered.connect(self._on_answer)
        bridge.docChanged.connect(self._refresh)
        bridge.selectionChanged.connect(self._on_selection)
        if getattr(viewport, "_r", None) is not None:
            viewport._r.ready.connect(self.picture_came)

    on = Property(bool, lambda s: s._on, notify=changed)
    can = Property(bool, lambda s: s._selected_canvas() is not None, notify=changed)   # Paint (B) is offered
    itemName = Property(str, lambda s: s._name(), notify=changed)
    layers = Property("QVariantList", lambda s: P.layer_rows(s._item() or {}, s._active), notify=changed)
    channels = Property("QVariantList", lambda s: P.channels(), constant=True)
    activeChannel = Property(str, lambda s: s._layer().get("channel", "colour") if s._layer() else "", notify=changed)
    brushObj = Property(QObject, lambda s: s.brush, constant=True)
    coverageObj = Property(QObject, lambda s: s.coverage, constant=True)   # "Seen by Hero 01: 62 % painted" + tint
    layerRowsObj = Property(QObject, lambda s: s.layerRows, constant=True)   # the chosen layer's Fill, Mask
    trail = Property("QVariantList", lambda s: s._trail, notify=trailChanged)       # parts of the viewport, 0..1
    cursorRadius = Property(float, lambda s: max(2.0, s.brush.values["size"] / 2 * (1.0 if s._by_view() or s._stamping() else s._ratio)),
                            notify=trailChanged)
    where = Property(str, lambda s: s._where, notify=changed)          # "surface" | "view" (the Brush group's switch)
    wheres = Property("QVariantList", lambda s: P.WHERE, constant=True)
    canStamp = Property(bool, lambda s: s._can_stamp(), notify=changed)    # Brush | Stamp shows (a Relief layer)
    how = Property(str, lambda s: s._how, notify=changed)
    hows = Property("QVariantList", lambda s: P.HOWS, constant=True)

    def _can_stamp(self) -> bool:
        return (self._layer() or {}).get("channel", "colour") == P.STAMP_CHANNEL

    def _stamping(self) -> bool:
        """A click lays one whole picture (paint.stamp) instead of a brush stroke."""
        return self._how == "stamp" and self._can_stamp()

    def _sync_stamp(self):
        self.brush.set_stamping(self._stamping())
        self.layerRows.refresh()                          # (the chosen layer, or its values, changed)

    # --- the mesh painted and its layers
    def _item(self):
        if not self._id or not self.b.doc.has(self._id):
            return None
        it = self.b.doc.item(self._id)
        return it if it.get("type") in P.CANVASES else None

    def _name(self):
        it = self._item()
        return self.b.label_of(it) if it else ""

    def _layer(self):
        it = self._item() or {}
        return next((p for p in it.get("paints", []) if p["id"] == self._active), None)

    def _refresh(self, *_):
        it = self._item()
        if self._on and it is None:
            return self.leave()
        if it is not None and self._layer() is None:     # the active layer went (undo, delete): the top one
            self._active = it["paints"][-1]["id"] if it.get("paints") else ""
        self._sync_stamp()
        self.changed.emit()

    def _on_selection(self, *_):
        if self._on and self.b.selected != self._id:
            self.leave()
        self.changed.emit()

    def _selected_canvas(self):
        sel = self.b.selection
        it = self.b.doc.item(sel[0]) if len(sel) == 1 and self.b.doc.has(sel[0]) else None
        return it if it is not None and it.get("type") in P.CANVASES else None

    # --- the mode
    @Slot()
    def toggle(self):
        self.leave() if self._on else self.enter()

    @Slot()
    def enter(self):
        it = self._selected_canvas()
        if it is None:
            return self.b.fail_line("Paint needs one mesh or clay selected.")
        self.v.mesh_edit.leave()
        self.v.clay_tool.leave()
        self._on, self._id = True, it["id"]
        self._refresh()
        if it["type"] == "mesh" and not it.get("uvs"):    # no unfolded surface yet: unfold it, nothing asked
            self.b.say(f"Unfolding {self._name()}…")
            QTimer.singleShot(30, self._unfold)          # the line shows before the engine works

    def _unfold(self):
        if self._item() is not None and self.b._guard(lambda: self.b._apply(
                [{"op": "mesh.unfold", "target": [self._id], "args": {}}], f"Unfold {self._name()}")):
            self.b.say("")

    @Slot()
    def leave(self):
        if self._on:
            self._on, self._trail, self._drag = False, [], self._drag + 1
            self.changed.emit()
            self.trailChanged.emit()
            if self.coverage.on:
                self.v._on_doc()                     # the tint is Paint's: the plain picture again

    @Slot()
    def addLayer(self):
        it = self._item()
        if it is None:
            return
        ch = self.activeChannel or "colour"
        before = {p["id"] for p in it.get("paints", [])}
        if self.b._guard(lambda: self.b._apply([{"op": "paint.add", "target": [it["id"]],
                                                  "args": P.new_layer_args(it, ch)}], "New paint layer")):
            self._active = next((p["id"] for p in self._item()["paints"] if p["id"] not in before), self._active)
            self.changed.emit()

    @Slot(str)
    def setWhere(self, where):
        if where in ("surface", "view") and where != self._where:
            self._where = where
            self.changed.emit()
            self.trailChanged.emit()                  # the brush disc's size follows (screen px From the view)

    @Slot(str)
    def setHow(self, how):
        if how in ("stroke", "stamp") and how != self._how:
            self._how = how
            self._sync_stamp()
            self.changed.emit()
            self.trailChanged.emit()                  # the brush disc's size follows (screen px on a mesh)

    @Slot(str)
    def setActive(self, layer_id):
        self._active = layer_id
        self._sync_stamp()
        self.changed.emit()

    @Slot(str)
    def setChannel(self, channel):
        layer = self._layer()
        if layer is not None and layer.get("channel", "colour") != channel:
            args = P.channel_args(self._item(), layer, channel)
            self.b._guard(lambda: self.b._apply([{"op": "paint.set", "target": [self._active], "args": args}],
                                                f"Paints: {P.CHANNELS[channel][0]}"))

    @Slot(str)
    def toggleVisible(self, layer_id):
        it = self._item() or {}
        layer = next((p for p in it.get("paints", []) if p["id"] == layer_id), None)
        if layer is not None:
            on = not layer.get("visible", True)
            self.b._guard(lambda: self.b._apply([{"op": "paint.set", "target": [layer_id], "args": {"visible": on}}],
                                                f"{'Show' if on else 'Hide'} {layer.get('name', layer_id)}"))
