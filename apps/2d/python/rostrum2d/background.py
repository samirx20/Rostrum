"""Painted backgrounds: the maths. How much of a layer at a depth the frame ever shows (so a background painted at
that depth is big enough), and the mapping between a drawing's canvas px and the composition's px (to move strokes
between depth layers). The one place these rules live; ops_background.py and mcp/background_tool.py use it.

The frame rule is apps/2d/FRAME.md › The maths, through frame/view.py (the same as the engine): with
s = 1 / (1 + depth), the export shows the layer's world px H + s·(F − H) ± (half the output) / zoom**s, turned by the roll.
"""
from __future__ import annotations

import math

from . import fields as F
from .cover import BLEED, edges
from .frame import view


def comp_size(comp: dict) -> tuple[float, float]:
    d = F.defaults("comp")
    return float(comp.get("width", d["width"])), float(comp.get("height", d["height"]))


def shots(comp: dict) -> list[tuple]:
    """The frame (view.Shot) at every frame of the composition (its keys, eases and ride included); at home for a
    scene made before frames."""
    d = F.defaults("comp")
    fps, dur = float(comp.get("fps", d["fps"])), float(comp.get("duration", d["duration"]))
    w, h = comp_size(comp)
    home = view.Shot(w / 2, h / 2, 1.0, 0.0, w / 2, h / 2)
    return [view.shot(comp, n / fps) or home for n in range(max(1, int(math.ceil(dur * fps))) + 1)]


def seen_box(comp: dict, depth: float, shot_list=None) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) in world px: everything of a layer at `depth` the frame shows over the whole composition."""
    w, h = comp_size(comp)
    s = 1 / (1 + depth)
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for x, y, zoom, roll, hx, hy in shot_list or shots(comp):
        z = zoom ** s
        r = math.radians(roll)
        hw = (w / 2 * abs(math.cos(r)) + h / 2 * abs(math.sin(r))) / z
        hh = (w / 2 * abs(math.sin(r)) + h / 2 * abs(math.cos(r))) / z
        px, py = hx + s * (x - hx), hy + s * (y - hy)
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
    """Plain words for each edge where the frame would see past a layer over the shot (cover.edges: its own turned
    box at each frame); [] = it covers."""
    fps = float(comp.get("fps", F.defaults("comp")["fps"]))
    return [f"{e['short']} px short on the {e['edge']}" + (f" from {e['from']:.1f} s" if e["from"] >= 0.05 else "")
            for e in edges(comp, layer, shot_list or shots(comp), fps)]


def depth_names(depths: list[float]) -> list[str]:
    """Far / Mid / Near for three planes, else Far, Mid 1 … Near, by order far → near."""
    n = len(depths)
    if n == 1:
        return ["Background"]
    if n == 2:
        return ["Far", "Near"]
    return ["Far", *(["Mid"] if n == 3 else [f"Mid {i}" for i in range(1, n - 1)]), "Near"]
