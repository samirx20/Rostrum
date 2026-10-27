"""The canvas handles' two drags: resize a layer from a corner or edge, and turn it. Each is one doc.gesture = one undo
step, made of the same value.set calls an agent makes (route.value_call: an animated field gets a key at the playhead,
a still one changes). The maths is transform.py. A slot mix-in for Bridge2D (see rostrum_gui/parts.py).

What a resize changes, per layer type: shapes and images change Width / Height (their own size); every other
type (group, text, video, drawing, path, ...) changes Scale (a corner) or Stretch X / Y (an edge). X / Y follow so the opposite
side stays put (Alt: the centre does), except in an auto layout, where the layout places the layer. Dragged past the
opposite side, a layer (a group too) mirrors (a negative Stretch) and keeps resizing.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Slot
from rostrum2d.evaluate import resolve
from rostrum_gui.drag import words_angle, words_size

from . import bounds, drag_chip, exprs, layout_drag, line_ends, picking, route, transform as T
from .shape_handle_slots import wraps

OWN_SIZE = ("shape", "image")                 # types whose Width / Height can be keyed (fields.py); a group is resized by Scale, so what is in it grows with it


@dataclass
class Grab:
    layer: str
    p: dict                                    # the layer's values at the playhead when the drag began
    box: dict                                  # its on-screen box then (bounds.boxes)
    hx: int = 0
    hy: int = 0
    placed: bool = False                       # an auto layout places it: no X / Y
    last: float | None = None                  # rotate: the pointer's last angle
    turned: float = 0.0
    kit: str = "box"                           # which handles it has (handle_kinds.py)


class HandleSlots:
    @Property(QObject, constant=True)
    def multi(self):
        """The layers selected together (multi.py)."""
        return self._multi

    @Property(QObject, constant=True)
    def dragChip(self):
        """The value chip by the pointer during a canvas drag (drag_chip.py; the kit's DragLabel in Stage.qml)."""
        return drag_chip.view_of(self)

    @Slot(float, float, result=str)
    def layerAt(self, x, y):
        """What a click at (x, y) composition px would select (picking.py), without selecting it ("" for none)."""
        return self._multi.target(x, y, "click")

    @Slot(float, float, bool, result="QVariantMap")
    def hoverAt(self, x, y, deep):
        """The Move tool's hover (Stage.qml's hover outline and pointer badges): what a press at (x, y) composition px
        would pick, by the press's own rule (multi.target: "click", or "deep" with Ctrl), with its box on screen
        ({x, y, w, h, rot, ax, ay}); `grouped`: Ctrl would pick a deeper piece there; `picked`: it is picked already.
        {} = nothing painted there. One look at the kept boxes, no picture made (~1 ms a move at 200 layers)."""
        chain = bounds.pick_chain(self.placed(), self._t, x, y)
        sel = self._multi.layers()[0] if self._multi.layers() else ""
        click = picking.choose(chain, sel, picking.groups_of(self.doc, sel) if sel else [], "click")
        hit = chain[-1] if deep and chain else click
        box = next(iter(self.shown_boxes([hit])), None) if hit else None
        if box is None:
            return {}
        return {**{k: box.get(k, 0) for k in ("x", "y", "w", "h", "rot", "ax", "ay")},
                "id": hit, "grouped": bool(chain) and chain[-1] != click, "picked": self._multi.has(hit)}

    @Slot(int, int, float, result=float)
    def resizeCursor(self, hx, hy, rot):
        """The angle of the `resize` pointer a knob shows on a layer turned `rot` degrees (transform.resize_cursor)."""
        return T.resize_cursor(hx, hy, rot)

    def _handle_grab(self, label, fields_of):
        layer = self.selectedLayer
        if not layer:
            return None
        item = self.doc.item(layer)
        box = next((b for b in bounds.boxes(self.placed(), self._t) if b["id"] == layer), None)
        if box is None or box["w"] <= 0 or box["h"] <= 0:
            self._fail(f"Error: {label}: this layer has no box to {label}.")
            return None
        placed = layout_drag.begin(self.doc, self.placed(), layer, self._t) is not None
        p = resolve(item, self.own_t(layer))
        g = Grab(layer, p, box, placed=placed, kit=box.get("handles", "box"))
        for prop in fields_of(g, item):
            if exprs.drives(item, prop):
                self._fail(f"Error: {label}: {prop} is driven by an expression; clear it first (the cross on its row).")
                return None
        return g

    def _handle_begin(self, label, hx, hy, fields_of) -> bool:
        g = self._handle_grab(label.split()[0].lower(), fields_of)
        if g is None:
            return False
        g.hx, g.hy = int(hx), int(hy)
        return self._begin(f"{label} {self.label_of(self.doc.item(g.layer))}", g)

    @Slot(int, int, result=bool)
    def beginResize(self, hx, hy):
        def fields_of(g, item):
            size = ("w", "rotation") if g.kit == "ends" else ("w", "h", "scaleX", "scaleY") if item["type"] in OWN_SIZE else ("scale", "scaleX", "scaleY")
            size += ("boxWidth",) if wraps(g) else ()
            return size + (() if g.placed else ("x", "y"))
        ok = self._handle_begin("Resize", hx, hy, fields_of)
        if ok and self._grab.kit != "ends":             # the dragged edge snaps (snapper.py); not on a turned box
            self._snap.begin_edge(self._grab.layer, abs(self._grab.box["rot"]) > 1e-6)
        return ok

    @Slot(float, float, bool, bool)
    def resizeBy(self, dx, dy, shift=False, alt=False):
        """Total drag from where it began, composition px. Corner or edge, Shift = same proportion, Alt = from the centre."""
        g = self._grab
        if self._drag is None or not isinstance(g, Grab):
            return
        item, p, b = self.doc.item(g.layer), g.p, g.box
        if g.kit == "ends":
            return self._end_by(g, item, dx, dy, shift, alt)
        dx, dy = self._snap.edge(g.hx, g.hy, dx, dy)
        if wraps(g) and not (g.hx and g.hy):                   # a text's side: its wrap width (shape_handle_slots.py)
            return self._wrap_by(g, item, dx, dy, alt)
        scaled = item["type"] not in OWN_SIZE
        dx, dy = bounds.parent_delta(b, dx, dy)                 # the drag in the layer's parent's px (a turned group)
        hx, hy, ax, ay = bounds.parent_side(b, g.hx, g.hy)    # inside a mirrored group the box runs the other way
        r = T.resize({"x": p["x"], "y": p["y"], "w": b["lw"], "h": b["lh"], "ax": ax, "ay": ay, "rot": b["lrot"]},
                     hx, hy, dx, dy, shift, alt, uniform=scaled)
        sets = {}
        if scaled and g.hx and g.hy:
            sets["scale"] = p["scale"] * r["w"] / b["lw"]
        elif scaled:
            sets.update({"scaleX": p["scaleX"] * r["w"] / b["lw"]} if g.hx else {"scaleY": p["scaleY"] * r["h"] / b["lh"]})
        else:
            sets.update({"w": p["w"] * r["w"] / b["lw"]} if g.hx else {})
            sets.update({"h": p["h"] * r["h"] / b["lh"]} if g.hy else {})
        for axis, crossed in (("scaleX", r["cx"]), ("scaleY", r["cy"])):      # past the opposite side: mirrored (a negative Stretch)
            if crossed:
                sets[axis] = -sets.get(axis, p[axis])
        if not g.placed:
            sets.update({"x": r["x"], "y": r["y"]})
        drag_chip.say(self, words_size(abs(r["w"]), abs(r["h"])), "resize", shift, alt)
        # fresh: on the values from before the drag, so a Stretch mirrored on one step and not on the next goes back
        self._guard(lambda: self._drag.preview([route.value_call(item, k, round(v, 2), self.own_t(item["id"])) for k, v in sets.items()], fresh=True))

    def _end_by(self, g, item, dx, dy, shift, alt):
        """A line's or arrow's end dragged: the end follows the pointer (line_ends.py); length and turn come with it."""
        p, b = g.p, g.box
        dx, dy = bounds.parent_delta(b, dx, dy)
        r = line_ends.drag_end({"x": p["x"], "y": p["y"], "w": b["lw"], "h": b["lh"], "ax": b["ax"], "ay": b["ay"],
                                "rot": b["lrot"]}, g.hx, dx, dy, shift, alt)
        sets = {"w": p["w"] * r["w"] / b["lw"], "rotation": r["rot"]}
        if not g.placed:
            sets.update({"x": r["x"], "y": r["y"]})
        self._guard(lambda: self._drag.preview([route.value_call(item, k, round(v, 2), self.own_t(item["id"])) for k, v in sets.items()]))

    @Slot(result=bool)
    def beginRotate(self):
        return self._handle_begin("Rotate", 0, 0, lambda g, item: ("rotation",))

    @Slot(float, float, bool)
    def rotateTo(self, px, py, shift=False):
        """The pointer's place in composition px: the layer turns about its anchor by the angle the pointer swept."""
        g = self._grab
        if self._drag is None or not isinstance(g, Grab):
            return
        b = g.box
        a = T.angle(b["x"] + b["ax"] * b["w"], b["y"] + b["ay"] * b["h"], px, py)
        g.turned += 0.0 if g.last is None else T.short(a - g.last)
        g.last = a
        item = self.doc.item(g.layer)
        turned = -g.turned if b.get("pm") else g.turned            # in a mirrored group, a turn on screen is the other way round in it
        drag_chip.say(self, words_angle(round(T.rotate(g.p["rotation"], turned, shift), 1)), "turn", shift)
        self._guard(lambda: self._drag.preview([route.value_call(item, "rotation", round(T.rotate(g.p["rotation"], turned, shift), 2), self.own_t(g.layer))]))
