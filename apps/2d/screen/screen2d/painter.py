"""The Draw tool's side of the screen: the pen, the brush, drawings frame by frame, the onion skin.

Every change is an operation recorded through the document (a stroke = one gesture; "new drawing" and "hold" =
one `doc.apply` each). The brush and the onion toggle are screen state. The brush panel is the kit's Inspector
on this object (it has the same `rows` / `setValue` / `toggleMore` surface as a DocBridge), so the panel is built
from the brush settings' own rules, not by hand.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d.drawing import frame_at, frame_number
from rostrum2d.ops_paint import PAINTABLE
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

from . import adding, framing, onion
from .brush import Brush
from .strokes import StrokeDrag


class Painter(QObject):
    changed = Signal()
    brushChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._stroke, self._onion = bridge, None, False
        self.brush = Brush(bridge.comp().get("background", ""))
        self._serial, self._built, self._rev = 0, None, 0        # _rev: the document changed (the onion is stale)
        self.provider = onion.OnionProvider()
        self.model = RowsModel(rows.ROLES, self)
        self.model.reset(self.brush.rows())
        bridge.docChanged.connect(self._doc_changed)
        bridge.outlineChanged.connect(self._refresh)

    # ---- reads for QML ----------------------------------------------------------------------------------------
    def target(self) -> dict | None:
        """The selected layer the pen paints on: a drawing, or any element that can hold paint (ops_paint.PAINTABLE)."""
        layer = self.b.selectedLayer
        item = self.b.doc.item(layer) if layer else None
        return item if item and item["type"] in PAINTABLE else None

    def drawing(self) -> dict | None:
        """The selected layer that has drawings (frame tools, onion): a drawing, or an element holding paint."""
        item = self.target()
        return item if item and (item["type"] == "drawing" or item.get("frames")) else None

    def _n(self) -> int:
        return frame_number(self.b.own_t(self.b.selectedLayer), self.b.comp()["fps"])

    @Property(str, notify=changed)
    def drawingId(self):
        d = self.drawing()
        return d["id"] if d else ""

    @Property("QVariantMap", notify=changed)
    def now(self):
        """Which drawing buttons apply at the playhead (see framing.state); {} with no drawing selected."""
        d = self.drawing()
        return framing.state(d, self._n()) if d else {}

    @Property("QVariantList", notify=changed)
    def frameMarks(self):
        d = self.drawing()
        return framing.marks(self.b.placed_item(d["id"]), self.b.comp()["fps"], self.b.comp()["duration"]) if d else []     # composition seconds

    @Property(bool, notify=changed)
    def onionOn(self):
        return self._onion

    @Property(int, notify=changed)
    def onionSerial(self):
        return self._serial if self._onion and self._built else 0

    # ---- the brush panel (the kit's Inspector talks to these) ---------------------------------------------------
    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property("QVariantMap", notify=brushChanged)
    def brushNow(self):
        """The context bar's quick brush controls (ActionBar.qml, Paint): the next stroke's values and the tips."""
        from rostrum_paint.marks import TIPS
        return {**self.brush.values, "tips": list(TIPS)}

    @Property("QVariantMap", notify=brushChanged)
    def selectedItem(self):
        return {"id": "brush", "label": self.brush.label(), "kind": "next stroke"}

    @Property(bool, notify=brushChanged)
    def moreOpen(self):
        return self.brush.more

    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        return self.b.guard(lambda: self._brush_set(param, value))

    def _brush_set(self, param, value):
        self.brush.set(param, value)
        self.model.update(self.brush.rows())
        self.brushChanged.emit()

    @Slot(str)
    def beginScrub(self, param):
        pass                                        # the brush is not the document: nothing to gather into a step

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        self.setValue(param, value)

    @Slot()
    def endScrub(self):
        pass

    @Slot()
    def toggleMore(self):
        self.brush.more = not self.brush.more
        self.model.update(self.brush.rows())
        self.brushChanged.emit()

    @Slot(str)
    def toggleAnimate(self, param):
        pass

    # ---- the pen: one stroke = one gesture = one change -----------------------------------------------------
    @Slot(float, float, float, result=bool)
    def beginStroke(self, x, y, pressure):
        """x, y in composition px (like Bridge2D.pickAt); pressure 0..1 (1 for a mouse)."""
        d = self.target()
        if d is None and self.b.tool != "draw":
            return False
        self.endStroke()
        c = self.b.comp()
        make = None
        if d is None:                       # Draw tool, no drawing selected: the first stroke makes the drawing layer too
            make, lid = adding.new_layer_calls(self.b.doc, c, "drawing")
            d = {"id": lid}

        def go():
            self._stroke = StrokeDrag(self.b.doc, self.b.who, d["id"], self.b.time if make else self.b.own_t(d["id"]), c["fps"],
                                      self.brush.stroke_args(), x, y, pressure, make)
            if make:
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
            self.b.guard(lambda: self.b.done(s.end(), ""))
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
