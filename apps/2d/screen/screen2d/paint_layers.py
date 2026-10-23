"""The settings panel's paint groups while Brush is on (painting design §2.3, mockup paint-02): Inside the outline and
Draw each frame (`toggles`), and "Paint layers +": the paint layers of the drawing the pen paints on now (eye,
thumbnail, name, its blend and opacity in grey when not Normal · 100 %, a lock when locked), top first. With one paint
layer only the "Paint layers +" line shows; + adds one on top, highlighted (the next stroke goes into it).

Every edit is one operation of the painting kit or the element's own field operation, one change and one undo step
each (paint.add, paint.set name / mode / opacity / visible / locked, paint.move, paint.remove, <type>.set); an opacity
scrub is one gesture. Which layer is highlighted is screen state: the pen's strokes and fills go on it (`current`).
Absent (empty) when the pen paints on a new drawing.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import paint_fields
from rostrum2d.drawing import canvas_size, each_frame, frame_at
from rostrum_gui.edits import Drag
from rostrum_paint.fields import LAYER_MODES

from .paint_thumbs import ThumbProvider


class PaintLayers(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._picked, self._drag = bridge, "", None
        self.thumbs = ThumbProvider()                     # image://paintthumbs (session.py)
        for sig in (bridge.docChanged, bridge.outlineChanged, bridge.toolChanged, bridge.frameChanged):
            sig.connect(self.changed)
        bridge.painter.changed.connect(self._painter_changed)

    def _painter_changed(self):
        if self.b.painter.newLayerNext:                   # + Paint layer: the new layer (on top) takes the next strokes
            self._picked = ""
        self.changed.emit()

    # ---- what is painted on ---------------------------------------------------------------------------------------
    def _item(self) -> dict | None:
        return self.b.painter._aim()                      # the selected element, unless "New drawing" was picked

    def _frame(self) -> dict | None:
        """The drawing the pen paints on now: the one at the playhead with Draw each frame on, else the one painting."""
        d = self._item()
        if not d or not d.get("frames"):
            return None
        return frame_at(d, self.b.painter._n()) if each_frame(d) else d["frames"][0]

    def current(self) -> str:
        """The highlighted paint layer's id when it is in the drawing at the playhead, else "" (the top unlocked one)."""
        f = self._frame()
        ids = [p["id"] for p in f["paints"]] if f else []
        return self._picked if self._picked in ids else ""

    # ---- reads for QML ----------------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def canAdd(self):
        """The "Paint layers +" line: once what the pen paints on holds paint (before that the first stroke makes one)."""
        return self._frame() is not None

    @Property("QVariantList", notify=changed)
    def layers(self):
        """Top first, as the list shows them: [{id, name, visible, locked, opacity, mode, note, thumb, current}];
        empty while there is one paint layer (nothing to choose between)."""
        f = self._frame()
        if not f or len(f["paints"]) < 2:
            return []
        now = self.current() or next((p["id"] for p in reversed(f["paints"]) if not p.get("locked")), "")
        w, h = canvas_size(self._item())
        return [{"id": p["id"], "name": p["name"], "visible": p["visible"], "locked": bool(p.get("locked")),
                 "opacity": p["opacity"], "mode": p["mode"], "note": _note(p), "current": p["id"] == now,
                 "thumb": "image://paintthumbs/" + self.thumbs.key(f, p, w, h) if w and h else ""}
                for p in reversed(f["paints"])]

    @Property("QVariantList", constant=True)
    def modes(self):
        return [{"value": m, "label": m.capitalize()} for m in LAYER_MODES]

    @Property("QVariantList", notify=changed)
    def toggles(self):
        """What the pen paints on's own paint switches: [{id, label, help, value}] (paint_fields): Inside the outline
        (an element: a drawing has no outline) and Draw each frame, from the first moment, before any paint, so an
        animation can start on an empty layer (painting design §2.2, §2.5)."""
        d = self._item()
        if not d:
            return []
        params = paint_fields.DRAWING if d["type"] == "drawing" else paint_fields.ELEMENT
        return [{"id": p.name, "label": p.label, "help": p.help, "value": d.get(p.name, p.default)}
                for p in params if p.type == "toggle"]

    @Property(bool, notify=changed)
    def onionApplies(self):
        d = self._item()
        return bool(d and d.get("frames") and each_frame(d))

    # ---- edits: one change each -------------------------------------------------------------------------------------
    def _apply(self, calls, label):
        self.b.guard(lambda: self.b.done(self.b.doc.apply(calls, self.b.who, label=label), ""))

    @Slot(str)
    def pick(self, paint_id):
        self._picked = paint_id
        self.changed.emit()

    @Slot()
    def add(self):
        """+ : a new paint layer on top ("Paint 2", "Paint 3" …), highlighted: the next stroke goes into it."""
        f = self._frame()
        if not f:
            return
        names, n = {p["name"] for p in f["paints"]}, len(f["paints"]) + 1
        while f"Paint {n}" in names:
            n += 1
        before = {p["id"] for p in f["paints"]}
        self._apply([{"op": "paint.add", "target": [f["id"]], "args": {"name": f"Paint {n}"}}], "Add paint layer")
        f = self._frame()
        self.pick(next((p["id"] for p in f["paints"] if p["id"] not in before), "") if f else "")

    @Slot(str, str, "QVariant")
    def setLayer(self, paint_id, name, value):
        label = {"name": "Rename paint layer", "locked": "Lock paint layer" if value else "Unlock paint layer",
                 "visible": "Show paint layer" if value else "Hide paint layer", "mode": "Paint layer blend"}
        self._apply([{"op": "paint.set", "target": [paint_id], "args": {name: value}}], label.get(name, "Paint layer"))

    @Slot(str)
    def remove(self, paint_id):
        self._apply([{"op": "paint.remove", "target": [paint_id]}], "Delete paint layer")

    @Slot(str, int)
    def moveTo(self, paint_id, row):
        """Dropped at `row` of the list (0 = top)."""
        f = self._frame()
        if f:
            self._apply([{"op": "paint.move", "target": [paint_id], "args": {"index": len(f["paints"]) - 1 - row}}],
                        "Reorder paint layers")

    @Slot(str, bool)
    def setToggle(self, name, value):
        d = self._item()
        if d:
            self._apply([{"op": f'{d["type"]}.set', "target": [d["id"]], "args": {name: value}}], "Paint")

    @Slot(str)
    def beginScrub(self, paint_id):
        self.endScrub()
        self.b.guard(lambda: setattr(self, "_drag", (paint_id, Drag(self.b.doc, self.b.who, "Paint layer opacity"))))

    @Slot(float)
    def scrub(self, value):
        if self._drag:
            pid, drag = self._drag
            self.b.guard(lambda: drag.preview([{"op": "paint.set", "target": [pid], "args": {"opacity": value}}]))

    @Slot()
    def endScrub(self):
        got, self._drag = self._drag, None
        if got:
            self.b.guard(lambda: self.b.done(got[1].end(), ""))


def _note(p: dict) -> str:
    """The grey words after a paint layer's name: its blend and opacity, only when not Normal · 100 %."""
    if p["mode"] == "normal" and p["opacity"] >= 0.995:
        return ""
    return f'{p["mode"].capitalize()} · {round(p["opacity"] * 100)} %'
