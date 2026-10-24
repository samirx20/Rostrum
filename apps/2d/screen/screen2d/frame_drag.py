"""Picking and moving the frame on the canvas (camera spec 4.4, 4.5; issues 6, 9, 10, 19): backend.frameDrag.

The frame is the scene's layer of type `camera` (rostrum2d.frame). C or a click on its name tab picks it; while it is
picked, a drag inside it (or on the tab) moves it, a corner square zooms it and the zone just outside a corner turns it.
Every move writes the frame's own fields through the ordinary edit path (route.value_call: a still field changes for
the whole piece, an animated one gets a key at the playhead), so an agent does the same with `value.set` / `key.add` on
the frame. One drag = one gesture = one undo step (drags.py `_begin` / endDrag). All points are world px.

    begin(kind, px, py, corner)   kind "move" | "zoom" | "turn"; (px, py) the press; corner 0-3 (top-left clockwise)
    moveBy(dx, dy)                the drag so far; snaps the frame's edges and centre to layers', its centre to home
    zoomTo(px, py, alt)           a corner at the pointer: bigger box = zoom down; about the centre (Alt: the opposite corner)
    turnTo(px, py, shift)         turns about the centre; Shift: 15° steps; within 2° of upright: upright
    end()                         one change; the status line says what moved and whether for the whole piece
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.keys import keys_of
from rostrum2d.evaluate import resolve
from rostrum2d.frame import view as frame_view

from . import bounds, route
from .frame_view import _size, quad_rect

SIGNS = ((-1, -1), (1, -1), (1, 1), (-1, 1))        # the corners, top-left clockwise, as frame_view / WorldFrame.qml
WORDS = {"move": "Moved", "zoom": "Zoomed", "turn": "Turned"}         # the status line after the drag
LABELS = {"move": "Move the frame", "zoom": "Zoom the frame", "turn": "Turn the frame"}   # the history's name
UPRIGHT = 2.0                                       # degrees within which a turn lands upright
STEP = 15.0                                         # Shift: the turn in steps of this many degrees


@dataclass
class Grab:
    frame: str
    kind: str
    x: float
    y: float
    zoom: float
    rot: float
    px: float
    py: float
    corner: int
    w: float                                        # the output's size (the box at zoom 1)
    h: float
    wrote: tuple = ()                               # the fields the last move wrote


def turned(rot: float, shift: bool) -> float:
    """The frame's turn as the pointer puts it: Shift snaps to 15° steps; near upright snaps upright."""
    if shift:
        return round(rot / STEP) * STEP
    upright = round(rot / 360.0) * 360.0
    return upright if abs(rot - upright) < UPRIGHT else round(rot, 1)


def zoomed(g: Grab, px: float, py: float, alt: bool) -> tuple[float, float, float]:
    """(x, y, zoom) with the grabbed corner under the pointer, the box keeping the output's shape: about the centre, or
    (Alt) about the opposite corner, which then stays put."""
    c, s = math.cos(math.radians(g.rot)), math.sin(math.radians(g.rot))
    sx, sy = SIGNS[g.corner]
    hw, hh = sx * g.w / g.zoom / 2, sy * g.h / g.zoom / 2
    ox, oy = c * hw - s * hh, s * hw + c * hh       # the corner from the centre
    ax, ay = (g.x - ox, g.y - oy) if alt else (g.x, g.y)
    cx, cy = g.x + ox - ax, g.y + oy - ay           # the corner from the anchor
    k = ((px - ax) * cx + (py - ay) * cy) / (cx * cx + cy * cy)
    zoom = min(100.0, max(0.01, g.zoom / max(k, 1e-6)))
    k = g.zoom / zoom
    return ax + k * (g.x - ax), ay + k * (g.y - ay), round(zoom, 4)


class FrameDrag(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        for sig in (bridge.docChanged, bridge.selectedItemsChanged):
            sig.connect(self.changed)

    def _frame(self) -> dict | None:
        return frame_view.of(self.b.comp())

    @Property(str, notify=changed)
    def id(self) -> str:
        """The scene's frame's id ("" for a scene without one)."""
        f = self._frame()
        return f["id"] if f else ""

    @Property(bool, notify=changed)
    def picked(self) -> bool:
        """The frame alone is picked: its handles show and a drag inside it moves it."""
        f = self._frame()
        return f is not None and self.b.selection == [f["id"]]

    @Slot()
    def pick(self):
        """C, a click on the name tab (and the Frame row): pick the frame; the Select tool, as its handles need it."""
        f = self._frame()
        if f is None:
            return self.b._fail("Error: frame: this scene has no frame.")
        self.b.setTool("move")
        self.b.select(f["id"])

    @Slot(str, float, float, int, result=bool)
    def begin(self, kind, px, py, corner=0):
        f = self._frame()
        if f is None or kind not in WORDS:
            self.b._fail(f"Error: frame drag: {'no frame in this scene' if f is None else repr(kind) + ' is not move, zoom or turn'}.")
            return False
        if f.get("locked"):
            self.b._fail("Error: the frame is locked (the lock on its Frame row); unlock it to move it.")
            return False
        p = resolve(self.b.placed_item(f["id"]), self.b._t)          # keys on a marker placed
        g = Grab(f["id"], kind, p["x"], p["y"], p["zoom"] or 1.0, p.get("rotation", 0.0), px, py, int(corner) % 4,
                 *_size(self.b.comp()))
        if not self.b._begin(LABELS[kind], g):
            return False
        if kind == "move":
            self._snap_begin(g)
        return True

    def _snap_begin(self, g: Grab):
        """What the frame may catch: home (its centre only, first), then every visible top-level layer's box. A turned
        frame snaps only its centre (its edges aren't its extent's)."""
        box = {"cx": g.x, "cy": g.y, "w": g.w / g.zoom, "h": g.h / g.zoom, "rot": g.rot}
        square = abs(g.rot / 90.0 - round(g.rot / 90.0)) < 1e-6
        start = quad_rect(box) if square else (g.x, g.y, g.x, g.y)
        f = self._frame()
        home = (f.get("homeX", g.w / 2), f.get("homeY", g.h / 2))
        targets = [(0, (home[0], home[1], home[0], home[1]))]
        targets += [(1, bounds.extent(b)) for b in bounds.boxes(self.b.placed(), self.b._t)
                    if not b["up"] and b["w"] > 0 and b["h"] > 0 and b["opacity"] > 0]
        self.b._snap.begin_box(start, targets)

    def _grab(self) -> Grab | None:
        g = self.b._grab
        return g if self.b._drag is not None and isinstance(g, Grab) else None

    def _write(self, g: Grab, values: dict):
        item, t = self.b.doc.item(g.frame), self.b.own_t(g.frame)
        g.wrote = tuple(values)
        self.b._guard(lambda: self.b._drag.preview([route.value_call(item, k, v, t) for k, v in values.items()]))

    @Slot(float, float)
    def moveBy(self, dx, dy):
        """The drag so far in world px (Shift straight, snapping unless Ctrl: backend.snap.keys)."""
        g = self._grab()
        if g is not None:
            dx, dy = self.b._snap.move(dx, dy)
            self._write(g, {"x": round(g.x + dx, 2), "y": round(g.y + dy, 2)})

    @Slot(float, float, bool)
    def zoomTo(self, px, py, alt):
        g = self._grab()
        if g is not None:
            x, y, zoom = zoomed(g, px, py, alt)
            self._write(g, {"zoom": zoom, **({"x": round(x, 2), "y": round(y, 2)} if alt else {})})

    @Slot(float, float, bool)
    def turnTo(self, px, py, shift):
        g = self._grab()
        if g is not None:
            a0, a1 = math.atan2(g.py - g.y, g.px - g.x), math.atan2(py - g.y, px - g.x)
            d = (math.degrees(a1 - a0) + 180.0) % 360.0 - 180.0
            self._write(g, {"rotation": turned(g.rot + d, shift)})

    @Slot()
    def end(self):
        """Let go: one change. "Moved the frame (whole piece)" when what it wrote has no keys, else "… at 2.00 s"."""
        g = self._grab()
        self.b.endDrag()
        if g is None or not g.wrote or self.b.statusFailed:
            return
        f = self.b.doc.item(g.frame)
        keyed = any(keys_of(f, k) for k in g.wrote)
        self.b._set_status(f"{WORDS[g.kind]} the frame " + (f"at {self.b._t:.2f} s" if keyed else "(whole piece)"))
