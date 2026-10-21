"""Painted backgrounds: the maths. How much of a layer at a depth the camera ever shows (so a background painted at
that depth is big enough), and the mapping between a drawing's canvas px and the composition's px (to move strokes
between depth layers). The one place these rules live; ops_background.py and mcp/background_tool.py use it.

The camera rule is apps/2d/CAMERA.md › The maths, through camera/view.py (the same as the engine): with
s = 1 / (1 + depth), the screen shows the layer's comp px C + s·(cam − C) ± (half screen) / zoom**s, turned by the roll.
"""
from __future__ import annotations

import math

from . import fields as F
from .camera import view

BLEED = 24          # px painted past the furthest edge the camera shows: a soft edge never reaches the frame


def comp_size(comp: dict) -> tuple[float, float]:
    d = F.defaults("comp")
    return float(comp.get("width", d["width"])), float(comp.get("height", d["height"]))


def shots(comp: dict) -> list[tuple]:
    """(x, y, zoom, roll) of the camera at every frame of the composition (cameras' keys and eases included);
    the resting shot (comp centre, zoom 1, no roll) for frames no camera shows."""
    d = F.defaults("comp")
    fps, dur = float(comp.get("fps", d["fps"])), float(comp.get("duration", d["duration"]))
    w, h = comp_size(comp)
    rest = (w / 2, h / 2, 1.0, 0.0)
    return [view.shot(comp, n / fps) or rest for n in range(max(1, int(math.ceil(dur * fps))) + 1)]


def seen_box(comp: dict, depth: float, shot_list=None) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) in comp px: everything of a layer at `depth` the camera shows over the whole composition."""
    w, h = comp_size(comp)
    s = 1 / (1 + depth)
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for x, y, zoom, roll in shot_list or shots(comp):
        z = zoom ** s
        r = math.radians(roll)
        hw = (w / 2 * abs(math.cos(r)) + h / 2 * abs(math.sin(r))) / z
        hh = (w / 2 * abs(math.sin(r)) + h / 2 * abs(math.cos(r))) / z
        px, py = w / 2 + s * (x - w / 2), h / 2 + s * (y - h / 2)
        x0, y0, x1, y1 = min(x0, px - hw), min(y0, py - hh), max(x1, px + hw), max(y1, py + hh)
    return x0, y0, x1, y1


def cover(comp: dict, depth: float, bleed: float = BLEED, shot_list=None) -> dict:
    """The drawing layer's fields that cover a layer at `depth` for the whole shot: canvas w, h (whole px) and the
    x, y of its centre (anchor 0.5, scale 1, so one canvas px = one comp px)."""
    x0, y0, x1, y1 = seen_box(comp, depth, shot_list)
    x0, y0, x1, y1 = math.floor(x0 - bleed), math.floor(y0 - bleed), math.ceil(x1 + bleed), math.ceil(y1 + bleed)
    return {"w": int(x1 - x0), "h": int(y1 - y0), "x": (x0 + x1) / 2, "y": (y0 + y1) / 2}


def canvas_box(layer: dict) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) in comp px that a drawing's canvas covers at rest (its scale and stretch, no rotation)."""
    sx, sy = _scales(layer)
    left = layer.get("x", 960.0) - layer.get("anchorX", 0.5) * layer.get("w", 1920) * sx
    top = layer.get("y", 540.0) - layer.get("anchorY", 0.5) * layer.get("h", 1080) * sy
    return left, top, left + layer.get("w", 1920) * sx, top + layer.get("h", 1080) * sy


def _scales(layer: dict) -> tuple[float, float]:
    s = layer.get("scale", 1.0)
    return s * layer.get("scaleX", 1.0), s * layer.get("scaleY", 1.0)


def to_comp(layer: dict, x: float, y: float) -> tuple[float, float]:
    """A drawing's canvas px -> comp px (at rest; its rotation and tilt are not used)."""
    left, top, _, _ = canvas_box(layer)
    sx, sy = _scales(layer)
    return left + x * sx, top + y * sy


def from_comp(layer: dict, x: float, y: float) -> tuple[float, float]:
    left, top, _, _ = canvas_box(layer)
    sx, sy = _scales(layer)
    return (x - left) / sx, (y - top) / sy


def size_ratio(src: dict, dst: dict) -> float:
    """How much bigger a stroke must be in `dst`'s canvas px to keep its size in comp px."""
    (a, b), (c, d) = _scales(src), _scales(dst)
    return math.sqrt((a * b) / (c * d))


def gaps(comp: dict, layer: dict, shot_list=None) -> list[str]:
    """Plain words for each edge where the camera would see past a drawing's canvas over the shot; [] = it covers."""
    x0, y0, x1, y1 = seen_box(comp, layer.get("depth", 0.0), shot_list)
    l, t, r, b = canvas_box(layer)
    out = []
    for name, short in (("left", l - x0), ("top", t - y0), ("right", x1 - r), ("bottom", y1 - b)):
        if short > 0.5:
            out.append(f"{short:.0f} px short on the {name}")
    return out


def depth_names(depths: list[float]) -> list[str]:
    """Far / Mid / Near for three planes, else Far, Mid 1 … Near, by order far → near."""
    n = len(depths)
    if n == 1:
        return ["Background"]
    if n == 2:
        return ["Far", "Near"]
    return ["Far", *(["Mid"] if n == 3 else [f"Mid {i}" for i in range(1, n - 1)]), "Near"]
