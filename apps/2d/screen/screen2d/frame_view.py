"""The frame's box on the canvas (Stage.qml's WorldFrame.qml draws it; the view fits to it).

The canvas is the world: the frame is a box in it that can move, zoom and turn (apps/2d/FRAME.md). This object gives that
box at the time of the picture ON SCREEN (shown.py: the overlays never run ahead of the picture), as numbers in world px,
and the world rects the view fits to (Ctrl+0: the frame where it is now; Shift+1: everything, with the frame's whole path).
It does no work while the view pans or zooms: the box changes only when the picture on screen does.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import fields as F
from rostrum2d.frame import view as frame_view

from . import bounds


def _size(comp: dict) -> tuple[float, float]:
    d, p = F.defaults("comp"), comp.get("props", comp)
    return float(p.get("width", d["width"])), float(p.get("height", d["height"]))


def box_at(comp: dict, t: float) -> dict:
    """The frame's box at time t in world px: centre, size (the output's size seen at the frame's zoom), turn in degrees
    (clockwise) and zoom. A scene without a frame: the output as it is, at home."""
    w, h = _size(comp)
    shot = frame_view.shot(comp, t)
    if shot is None:
        return {"cx": w / 2, "cy": h / 2, "w": w, "h": h, "rot": 0.0, "zoom": 1.0}
    z = shot.zoom or 1.0
    return {"cx": shot.x, "cy": shot.y, "w": w / z, "h": h / z, "rot": shot.roll, "zoom": z}


def quad_rect(b: dict) -> tuple[float, float, float, float]:
    """x0, y0, x1, y1 round the box's four corners (turned about its centre)."""
    c, s = math.cos(math.radians(b["rot"])), math.sin(math.radians(b["rot"]))
    hw, hh = b["w"] / 2, b["h"] / 2
    pts = [(b["cx"] + c * x - s * y, b["cy"] + s * x + c * y) for x, y in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


def label_of(b: dict, w: float, h: float) -> str:
    """The name tab: the size at home, the zoom (1.4×, 0.80×) once the frame is zoomed."""
    if abs(b["zoom"] - 1.0) < 1e-3:
        return f"Frame · {round(w)} × {round(h)}"
    z = f"{b['zoom']:.2f}".rstrip("0").rstrip(".")
    if b["zoom"] < 1 and len(z) == 3:
        z += "0"                                    # 0.8 → 0.80: two decimals under 1
    return f"Frame · {z}×"


def _rect(x0, y0, x1, y1) -> dict:
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


class FrameView(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self._bridge, self._at = bridge, None
        bridge.shownChanged.connect(self.changed)
        bridge.outlineChanged.connect(self.changed)

    def _now(self) -> tuple[dict, dict]:
        """(the box, the composition) of the picture on screen; worked out once per picture."""
        placed, t = self._bridge.shown_placed(), self._bridge.shown_t()
        if self._at is None or self._at[0] is not placed or self._at[1] != t:
            self._at = (placed, t, box_at(placed, t))
        return self._at[2], placed

    @Property("QVariantMap", notify=changed)
    def box(self):
        return self._now()[0]

    @Property(str, notify=changed)
    def label(self):
        b, comp = self._now()
        return label_of(b, *_size(comp))

    @Slot(result="QVariantMap")
    def fitRect(self):
        """The frame's quad bounding box at the playhead (Ctrl+0)."""
        return _rect(*quad_rect(self._now()[0]))

    @Slot(result="QVariantMap")
    def everythingRect(self):
        """Every top-level layer's box united with the frame's whole path (Shift+1)."""
        comp = self._now()[1]
        w, h = _size(comp)
        fps = float(comp.get("props", comp).get("fps", 30)) or 30.0
        dur = float(comp.get("props", comp).get("duration", 5.0))
        rects = [bounds.extent(b) for b in self._bridge.shown_boxes() if not b["up"]]
        rects += [quad_rect(box_at(comp, i / fps)) for i in range(int(round(dur * fps)) + 1)]
        if not rects:
            return _rect(0, 0, w, h)
        xs0, ys0, xs1, ys1 = zip(*rects)
        return _rect(min(xs0), min(ys0), max(xs1), max(ys1))
