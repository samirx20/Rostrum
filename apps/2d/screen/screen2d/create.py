"""The creation tools: Rectangle (R), Ellipse (O), Text (T), and typing on the canvas (backend.create).

Shapes: press-drag-release on the canvas draws one at that place and size: one change ("Draw rectangle"), selected,
the tool back to Move. Shift = square / circle, Alt = from the centre, a click under `slop` = 200 x 200 centred on it.
Text: a click starts a text there (left-aligned, it grows as you type), a dragged box wraps inside; typing is one
undo step (typing_session.py). All coordinates in and out are composition px; the screen maps them (Stage's mapping only).
`box` is the live outline / typing box for QML: {kind, x, y, w, h, label} (x, y = its top-left). Every action is
also a plain operation (`layer.add` + the type's field operation) that agents call themselves.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import fields as F

from . import adding, bounds
from .typing_session import Session

DEFAULT_SIZE = 200.0                       # a click without a drag: this big
LABELS = {"rect": "rectangle", "ellipse": "ellipse"}
LOOK = ("font", "weight", "size", "color", "align")


def shape_box(x0, y0, x1, y1, shift=False, alt=False) -> tuple[float, float, float, float]:
    """The dragged box as (centre x, centre y, w, h): Shift = square (the longer side), Alt = pressed point is the centre."""
    dx, dy = x1 - x0, y1 - y0
    if shift:
        side = max(abs(dx), abs(dy))
        dx, dy = side * (1 if dx >= 0 else -1), side * (1 if dy >= 0 else -1)
    if alt:
        return x0, y0, 2 * abs(dx), 2 * abs(dy)
    return x0 + dx / 2, y0 + dy / 2, abs(dx), abs(dy)


class Create(QObject):
    boxChanged = Signal()
    typingChanged = Signal()
    canEditChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b, self._press, self._box, self._text, self._style = bridge, None, {}, None, {}
        bridge.toolChanged.connect(self._tool_changed)
        bridge.selectionChanged.connect(self.canEditChanged)        # canEdit follows the selection and the typing
        self.typingChanged.connect(self.canEditChanged)

    # ---- reads for QML ------------------------------------------------------------------------------------------
    @Property("QVariantMap", notify=boxChanged)
    def box(self):
        """The shape being dragged, or the text being typed in (see the module note); {} = nothing."""
        return self._box

    @Property(bool, notify=typingChanged)
    def typing(self):
        return self._text is not None

    @Property("QVariantMap", notify=typingChanged)
    def style(self):
        """The typing box's look (the context bar's Font, Weight, Size, Colour): the layer's own while editing; the
        remembered start look (or the defaults) for a new text. {} when not typing."""
        if self._text is None:
            return {}
        item = self.b.doc.item(self._text.id) if self.b.doc.has(self._text.id) else {}
        d = {k: F.defaults("text")[k] for k in LOOK}
        d["size"] = self._start_size()
        return {**d, **self._style, **{k: item[k] for k in d if k in item}}

    @Property(bool, notify=canEditChanged)
    def canEdit(self):
        """The selection is one text, not being typed in: Enter (or a double-click) types in it on the canvas."""
        sel = self.b.selected
        return self._text is None and bool(sel) and self.b.doc.has(sel) and self.b.doc.item(sel)["type"] == "text"

    @Property(str, notify=typingChanged)
    def body(self):
        """The words so far (an edit starts with the text's own)."""
        return self._text.body if self._text else ""

    def _start_size(self) -> float:
        return self._style.get("size") or max(8, round(self.b.comp()["height"] * 0.08 / 4) * 4)

    # ---- shapes -------------------------------------------------------------------------------------------------
    @Slot(str, float, float, float)
    def beginShape(self, kind, x, y, slop):
        if kind not in LABELS:
            return self.b._fail(f"Error: shape: {kind!r} is not a shape here (rect, ellipse).")
        self._press = (kind, x, y, slop)
        self._set_box({})

    @Slot(float, float, bool, bool)
    def dragShape(self, x, y, shift, alt):
        if self._press is None:
            return
        kind, x0, y0, slop = self._press
        if abs(x - x0) + abs(y - y0) <= slop:
            return self._set_box({})
        cx, cy, w, h = shape_box(x0, y0, x, y, shift, alt)
        self._set_box({"kind": kind, "x": cx - w / 2, "y": cy - h / 2, "w": w, "h": h, "label": f"{round(w)} × {round(h)}"})

    @Slot(float, float, bool, bool)
    def endShape(self, x, y, shift, alt):
        if self._press is None:
            return
        kind, x0, y0, slop = self._press
        self._press = None
        self._set_box({})
        click = abs(x - x0) + abs(y - y0) <= slop
        cx, cy, w, h = (x0, y0, DEFAULT_SIZE, DEFAULT_SIZE) if click else shape_box(x0, y0, x, y, shift, alt)
        if w < 1 or h < 1:
            return self.b._fail("Error: shape: draw it at least 1 px wide and high (hold Alt to draw from the centre).")
        self.addShape(kind, cx, cy, w, h)

    @Slot(str, float, float, float, float)
    def addShape(self, kind, cx, cy, w, h):
        """The operation behind the tool: one layer, `{shape, x, y, w, h}` at its centre, selected, one change."""
        calls, lid = adding.new_layer_calls(self.b.doc, self.b.comp(), "shape")
        calls[1]["args"].update({"shape": kind, "w": round(w, 2), "h": round(h, 2), "x": round(cx, 2), "y": round(cy, 2)})
        if self.b.guard(lambda: self.b.done(self.b.doc.apply(calls, self.b.who, label=f"Draw {LABELS[kind]}"), "")):
            self.b.select(lid)
            self.b.setTool("move")

    # ---- text ---------------------------------------------------------------------------------------------------
    @Slot(float, float, float)
    def beginText(self, x, y, width):
        """Start typing at (x, y) (the text's top-left); width > 0 = a box the words wrap in."""
        self.finish()
        place = {"x": round(x, 2), "y": round(y, 2), "anchorX": 0, "anchorY": 0, "align": "left"}
        if width > 0:
            place["boxWidth"] = round(width, 2)
        self._text = Session(self.b, None, {"size": self._start_size(), **self._style}, place)
        self.b.select("")
        self._text_box()

    @Slot(str)
    def editText(self, layer_id):
        """Type in an existing text again (double-click): `text.set {body}`, one change; empty or unchanged = nothing."""
        if self.b.doc.has(layer_id) and self.b.doc.item(layer_id)["type"] == "text":
            self.finish()
            self._text = Session(self.b, layer_id, {}, {})
            self.b.select(layer_id)
            self._text_box()

    @Slot(float, float, result=bool)
    def editAt(self, x, y):
        """Double-click at (x, y): type in the text painted there. False when it isn't a text."""
        hit = self.b._multi.target(x, y, "in")
        if hit and self.b.doc.item(hit)["type"] == "text":
            self.editText(hit)
            return True
        return False

    @Slot(str)
    def typeText(self, body):
        """Every key: the words so far (the picture shows them as they are typed; no history step yet)."""
        if self._text is not None:
            self.b.guard(lambda: self._text.type(body))
            self._text_box()

    @Slot(str, "QVariant")
    def setStyle(self, name, value):
        """Font / weight / size / colour while typing: in the same change, and the start look of the next text."""
        if name in LOOK and self._text is not None:
            self._style[name] = value
            self.b.guard(lambda: self._text.restyle(name, value))
            self._text_box()

    @Slot(str)
    def commitText(self, body):
        """End typing (Esc, Ctrl+Enter, a click elsewhere) with the box's final words."""
        if self._text is not None and body != self._text.body:
            self.typeText(body)
        self.finish()

    @Slot()
    def cancelText(self):
        """Throw the session away (nothing changes)."""
        if self._text is not None and self._text.drag is not None:
            self._text.drag.end(cancel=True)
        self._end()

    def finish(self):
        """Save the session as one change; the text stays, selected. Nothing typed (or empty) saves nothing."""
        s = self._text
        if s is None:
            return
        if s.drag is None:
            return self._end()
        if self.b.guard(lambda: self.b.done(s.end(), "")):
            if self.b.doc.has(s.id) and s.body.strip():
                self.b.select(s.id)
        else:
            s.drag.end(cancel=True)
        self._end()

    def _end(self):
        self._text = None
        self._set_box({})
        self.typingChanged.emit()
        if self.b.tool == "text":
            self.b.setTool("move")

    def _text_box(self):
        """Where the typing happens now: the text's box as laid out, or the click point until a letter is typed."""
        s = self._text
        mine = None
        if s is not None and self.b.doc.has(s.id):
            mine = next((x for x in bounds.boxes(self.b.placed(), self.b._t) if x["id"] == s.id), None)
        p = s.place if s else {}
        wrap = bool((self.b.doc.item(s.id).get("boxWidth") if s and s.layer else p.get("boxWidth")) or 0)
        if mine:
            box = {"kind": "text", "x": mine["x"], "y": mine["y"], "w": mine["w"], "h": mine["h"], "wrap": wrap}
        else:
            box = {"kind": "text", "x": p.get("x", 0), "y": p.get("y", 0), "w": p.get("boxWidth", 0),
                   "h": self._start_size(), "wrap": wrap}
        self._set_box(box)
        self.typingChanged.emit()

    def _set_box(self, box):
        self._box = box
        self.boxChanged.emit()

    def _tool_changed(self):
        self._press = None
        if self._text is not None:          # any tool change ends typing (the tool strip, a key): the text is kept
            self.finish()
        elif self.b.tool not in LABELS:
            self._set_box({})
