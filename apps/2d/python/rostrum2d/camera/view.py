"""The camera's maths, the same as the engine's (engine/render/src/camera/mod.rs; apps/2d/CAMERA.md › The maths), for
the look tools that place layers from the document without drawing (mcp/geometry.py). Matrices are (a, b, c, d, e, f):
a point (x, y) goes to (a·x + c·y + e, b·x + d·y + f), y down, turns clockwise."""
from __future__ import annotations

import math

from .. import fields as F
from ..evaluate import value_at

ID = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def shot(comp: dict, t: float):
    """(x, y, zoom, roll) of the camera showing at t, or None. Two showing at once: the later one in the list wins."""
    for layer in reversed(comp.get("layers", [])):
        if layer["type"] == "camera" and value_at(layer, "start", t) <= t < value_at(layer, "end", t):
            return tuple(float(value_at(layer, f, t)) for f in ("x", "y", "zoom", "rotation"))
    return None


def layer_matrix(comp: dict, cam, props: dict) -> tuple:
    """Where a top-level layer's comp px land on screen, for the camera `cam` (from `shot`) and the layer's values at
    the time: screen = C + R(-roll) * zoom**s * (p - C - s * (cam - C)), s = 1 / (1 + depth)."""
    if cam is None or props.get("screenLock"):
        return ID
    d = F.defaults("comp")
    cx, cy = comp.get("width", d["width"]) / 2, comp.get("height", d["height"]) / 2
    x, y, zoom, roll = cam
    s = 1 / (1 + props.get("depth", 0.0))
    z = zoom ** s
    r = math.radians(-roll)
    cos, sin = math.cos(r) * z, math.sin(r) * z
    px, py = cx + s * (x - cx), cy + s * (y - cy)
    return (cos, sin, -sin, cos, cx - cos * px + sin * py, cy - sin * px - cos * py)


def undo(m, x: float, y: float) -> tuple[float, float]:
    """A screen point back to comp px, through the inverse of the matrix `m` (the engine's `bones` reply gives each
    rig's as `camera`)."""
    a, b, c, d, e, f = m
    det = a * d - b * c
    x, y = x - e, y - f
    return ((d * x - c * y) / det, (a * y - b * x) / det)
