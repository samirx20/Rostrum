"""The Draw tool's side of the screen: the pen, the brush, drawings frame by frame, the onion skin.

Every change is an operation recorded through the document (a stroke = one gesture; "new drawing" and "hold" =
one `doc.apply` each). The brush and the onion toggle are screen state. The brush panel is the kit's Inspector
on this object (brush_panel.py), so the panel is built from the brush settings' own rules, not by hand.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum2d.drawing import each_frame, frame_at, frame_number
from rostrum2d.names import display_name
from rostrum2d.ops_paint import PAINTABLE
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

from . import adding, framing, onion
from .brush import Brush
from .brush_panel import BrushPanel
from .strokes import StrokeDrag


class Painter(BrushPanel):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._stroke, self._onion = bridge, None, False
        self._fresh, self._new_layer = None, False      # "New drawing" picked for this selection; next stroke: new paint layer
        self._target = None                             # (document state, layer, what the pen paints on): target()
        self.brush = Brush(bridge.comp().get("background", ""))
        self._serial, self._built, self._rev = 0, None, 0        # _rev: the document changed (the onion is stale)
        self.provider = onion.OnionProvider()
        self.model = RowsModel(rows.ROLES, self)
        self.model.reset(self.brush.rows())
        bridge.docChanged.connect(self._doc_changed)
        bridge.outlineChanged.connect(self._refresh)
        self.changed.connect(self.brushChanged)         # the header names what the pen paints on

    # ---- reads for QML ----------------------------------------------------------------------------------------
    def target(self) -> dict | None:
        """The selected layer the pen paints on: a drawing, or any element that can hold paint (ops_paint.PAINTABLE)."""
        layer, data, got = self.b.selectedLayer, self.b.doc.data, self._target
        if got is None or got[0] is not data or got[1] != layer:     # once per document state (never changed in place)
            item = self.b.doc.item(layer) if layer else None
            got = self._target = (data, layer, item if item and item["type"] in PAINTABLE else None)
        return got[2]

    def drawing(self) -> dict | None:
        """The selected layer that has drawings (frame tools, onion): a drawing, or an element holding paint."""
        item = self.target()
        return item if item and (item["type"] == "drawing" or item.get("frames")) else None

    def _n(self) -> int:
        return frame_number(self.b.own_t(self.b.selectedLayer), self.b.comp()["fps"])

    @Property(str, notify=changed)
    def drawingId(self):
        """The selected frame-by-frame layer (Draw each frame on): only it shows the timeline's frame tools (UX_SPEC
        3.9). Alt+N works on any painted element (it turns Draw each frame on): it reads drawing(), not this."""
        d = self.drawing()
        return d["id"] if d and each_frame(d) else ""

    @Property("QVariantMap", notify=changed)
    def now(self):
        """Which drawing buttons apply at the playhead (see framing.state); {} with no drawing selected."""
        d = self.drawing()
        return framing.state(d, self._n()) if d else {}

    @Property("QVariantList", notify=changed)
    def frameMarks(self):
        d = self.drawing()
        return framing.marks(self.b.placed_item(d["id"]), self.b.comp()["fps"], self.b.comp()["duration"]) if d else []     # composition seconds

    onionOn = Property(bool, lambda self: self._onion, notify=changed)

    @Property(int, notify=changed)
    def onionSerial(self):
        return self._serial if self._onion and self._built else 0

    # ---- what the pen paints on (PaintTarget.qml: "Painting on · Layer ▾") ---------------------------------------
    def _aim(self) -> dict | None:
        """The target, unless "New drawing" was picked for this selection."""
        return None if self._fresh == self.b.selectedLayer and self._fresh is not None else self.target()

    @Property(str, notify=changed)
    def targetName(self):
        d = self._aim()
        return display_name(d) if d else "New drawing"

    @Property(str, notify=changed)
    def targetValue(self):
        """Which of targetChoices is on: "selected" or "new"."""
        return "selected" if self._aim() else "new"

    @Property("QVariantList", notify=changed)
    def targetChoices(self):
        """Painting on › Layer ▾: the selected layer, the other painted layers (newest first), New drawing."""
        d = self.target()
        painted = [it for it in reversed(list(self.b.doc.items())) if it["type"] in PAINTABLE
                   and (it["type"] == "drawing" or it.get("frames")) and (not d or it["id"] != d["id"])]
        return ([{"value": "selected", "label": display_name(d)}] if d else []) +             [{"value": it["id"], "label": display_name(it)} for it in painted] + [{"value": "new", "label": "New drawing"}]

    @Slot(str)
    def paintOn(self, which):
        """"new": the next stroke makes a new drawing (for this selection); "selected": back to the selected layer;
        another layer's id: it is selected, so the pen paints on it."""
        if which not in ("new", "selected"):
            self._fresh = None
            self.b.select(which)
        else:
            self._fresh = self.b.selectedLayer if which == "new" else None
        self.changed.emit()

    @Property(bool, notify=changed)
    def canNewLayer(self):
        d = self._aim()
        return bool(d and d.get("frames"))

    newLayerNext = Property(bool, lambda self: self._new_layer, notify=changed)

    @Slot()
    def newPaintLayer(self):
        """The next stroke starts a new paint layer on top (paint.stroke layer "new"); pressed again: not."""
        self._new_layer = not self._new_layer
        self.changed.emit()

    # ---- the pen: one stroke = one gesture = one change -----------------------------------------------------
    @Slot(float, float, float, result=bool)
    def beginStroke(self, x, y, pressure):
        """x, y in composition px (like Bridge2D.pickAt); pressure 0..1 (1 for a mouse)."""
        d = self._aim()
        if d is None and self.b.tool != "draw":
            return False
        self.endStroke()
        c = self.b.comp()
        make = None
        if d is None:                       # Draw tool, no drawing selected: the first stroke makes the drawing layer too
            make, lid = adding.new_layer_calls(self.b.doc, c, "drawing")
            d = {"id": lid}
        layer = "new" if self._new_layer else self.b._paint_layers.current()     # the highlighted paint layer

        def go():
            self._stroke = StrokeDrag(self.b.doc, self.b.who, d["id"], self.b.time if make else self.b.own_t(d["id"]), c["fps"],
                                      self.brush.stroke_args(), x, y, self.b.place_of, pressure, make, layer)
            if make:
                self._fresh = None
                self.b.select(d["id"])
        return self.b.guard(go)

    @Slot(float, float, float)
    def strokeTo(self, x, y, pressure):
        if self._stroke is not None:
            self.b.guard(lambda: self._stroke.move(x, y, pressure))

    @Slot()
    def endStroke(self):
        s, self._stroke = self._stroke, None
        if s is not None:
            if self.b.guard(lambda: self.b.done(s.end(), "")):
                self._new_layer = False             # the new paint layer is made: later strokes go on it
            self._refresh()

    # ---- frame by frame (screen shortcuts and buttons; each is one change) -----------------------------------
    def _frame_edit(self, make):
        d = self.drawing()
        if d is not None:
            calls, label = make(d)
            self.b.guard(lambda: self.b.done(self.b.doc.apply(calls, self.b.who, label=label), ""))

    @Slot(bool)
    def newFrame(self, copy):
        self._frame_edit(lambda d: framing.new_frame(d, self._n(), copy))

    @Slot()
    def clearDrawing(self):
        """Wipe the drawing at the playhead (every paint layer's strokes) to redraw it: one change."""
        def calls(d):
            here = frame_at(d, self._n())
            return [{"op": "paint.clear", "target": [p["id"] for p in here["paints"]]}] if here else [], "Clear drawing"
        self._frame_edit(calls)

    @Slot(int)
    def holdBy(self, delta):
        self._frame_edit(lambda d: framing.hold(d, self._n(), delta))

    @Slot(int)
    def goFrame(self, direction):
        """-1 previous drawing, +1 next: the playhead jumps to where it starts."""
        d = self.drawing()
        at = framing.state(d, self._n())["prev" if direction < 0 else "next"] if d else None
        if at is not None:
            self.b.setTime(at / self.b.comp()["fps"] + self.b.offset(d["id"]))

    @Slot(bool)
    def setOnion(self, on):
        self._onion, self._built = on, None
        self._refresh()

    # ---- inside -----------------------------------------------------------------------------------------------
    def _doc_changed(self):
        self._rev += 1

    def _refresh(self):
        if self._stroke is None:                    # not while a stroke is being drawn: the neighbours don't change
            self._rebuild_onion()
        self.changed.emit()

    def _rebuild_onion(self):
        d = self.drawing()
        if not (self._onion and d):
            return
        here = frame_at(d, self._n())
        key = (d["id"], here and here["id"], self._rev)
        if key == self._built:
            return
        image = onion.build(d, self._n())
        self._built = key
        self.provider.put(image if image is not None else onion.QImage())
        self._serial += 1
