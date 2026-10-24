"""Fill (G while Draw is on; UX_SPEC.md §3.8): a click inside a closed area of the painting fills it with the brush's
colour and opacity, on the highlighted paint layer (or a new one when + Paint layer is armed): one `paint.fill`, one
change. Close gaps (small, medium, large) is screen state, like the brush. A click with nothing closed to fill is
refused by the operation and said in the status; nothing changes.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_paint.fill import GAPS

from . import flat_cue


class Filler(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._on, self._gap = bridge, False, next(iter(GAPS))
        bridge.toolChanged.connect(lambda: self.setOn(False))     # another tool (V, P, R …): Fill is off when Draw comes back

    on = Property(bool, lambda self: self._on, notify=changed)
    gap = Property(str, lambda self: self._gap, notify=changed)

    @Property("QVariantList", constant=True)
    def gaps(self):
        return [{"value": g, "label": g.capitalize()} for g in GAPS]

    @Slot(bool)
    def setOn(self, on):
        if on != self._on:
            self._on = on
            self.changed.emit()

    @Slot(str)
    def setGap(self, gap):
        self._gap = gap
        self.changed.emit()

    @Slot(float, float, result=bool)
    def fillAt(self, x, y):
        """x, y in composition px (like the pen's press)."""
        p = self.b.painter
        d = p._aim()
        if d is None or not d.get("frames"):               # the Fill button is absent then; a script still hears why
            self.b._fail("Fill: nothing painted to fill on; select a drawing or a painted element first")
            return False
        brush = p.brush.values
        args = {"at": [[x, y]], "gap": self._gap, "color": brush["color"], "opacity": brush["opacity"],
                "layer": "new" if p.newLayerNext else self.b._paint_layers.current(),
                "frame": max(0, p._n())}

        def go():
            place, before = self.b.place_of(d["id"]), self.b._paint_layers._frame()
            self.b.done(self.b.doc.apply([{"op": "paint.fill", "target": [d["id"]], "args": args}], self.b.who,
                                         label="Fill"), "")
            # the exact picture takes 1 to 3 s: the fill's flat colour shows now, until it lands (flat_cue.py)
            p.wet.flat(flat_cue.for_layer(self.b, d["id"], flat_cue.new_items(before, self.b._paint_layers._frame()), place),
                        lambda: self.b._waiting is None)
            if p.newLayerNext:
                p.newPaintLayer()                       # the new paint layer is made: later fills and strokes go on it
        return self.b.guard(go)
