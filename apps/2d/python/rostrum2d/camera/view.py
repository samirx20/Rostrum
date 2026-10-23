"""The camera's maths, the same as the engine's (engine/render/src/camera/mod.rs; apps/2d/CAMERA.md › The maths), for
the look tools that place layers from the document without drawing (mcp/geometry.py). Matrices are (a, b, c, d, e, f):
a point (x, y) goes to (a·x + c·y + e, b·x + d·y + f), y down, turns clockwise."""
from __future__ import annotations

import math

from .. import fields as F
from ..evaluate import value_at

ID = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def shot(comp: dict, t: float, at=value_at):
    """(x, y, zoom, roll) of the camera showing at t, or None. Two showing at once: the later one in the list wins.
    `at(layer, field, t)` reads a field: the document's layers by default (a camera riding a path where the ride puts
    it, follow.taken); the Lottie export passes the scene's."""
    for layer in reversed(comp.get("layers", [])):
        if layer["type"] == "camera" and at(layer, "start", t) <= t < at(layer, "end", t):
            got = {f: float(at(layer, f, t)) for f in ("x", "y", "zoom", "rotation")}
            if at is value_at and layer.get("ridePath"):
                from ..follow import taken      # follow imports the field tables, which import this package
                got.update(taken(layer, comp["layers"], t) or {})
            return got["x"], got["y"], got["zoom"], got["rotation"]
    return None


def parts(cx: float, cy: float, cam, depth: float) -> tuple[float, float, float, float]:
    """The camera's matrix for a layer at `depth` as a transform: (px, py, scale, turn). The comp point (px, py) lands
    on the centre (cx, cy), scaled by `scale` and turned by `turn` degrees (clockwise) about it. At rest: (cx, cy, 1, 0)."""
    if cam is None:
        return cx, cy, 1.0, 0.0
    x, y, zoom, roll = cam
    s = 1 / (1 + depth)
    return cx + s * (x - cx), cy + s * (y - cy), zoom ** s, -roll


def layer_matrix(comp: dict, cam, props: dict) -> tuple:
    """Where a top-level layer's comp px land on screen, for the camera `cam` (from `shot`) and the layer's values at
    the time: screen = C + R(-roll) * zoom**s * (p - C - s * (cam - C)), s = 1 / (1 + depth)."""
    if cam is None or props.get("screenLock"):
        return ID
    d = F.defaults("comp")
    cx, cy = comp.get("width", d["width"]) / 2, comp.get("height", d["height"]) / 2
    px, py, z, turn = parts(cx, cy, cam, props.get("depth", 0.0))
    r = math.radians(turn)
    cos, sin = math.cos(r) * z, math.sin(r) * z
    return (cos, sin, -sin, cos, cx - cos * px + sin * py, cy - sin * px - cos * py)


def undo(m, x: float, y: float) -> tuple[float, float]:
    """A screen point back to comp px, through the inverse of the matrix `m` (the engine's `bones` reply gives each
    rig's as `camera`)."""
    a, b, c, d, e, f = m
    det = a * d - b * c
    x, y = x - e, y - f
    return ((d * x - c * y) / det, (a * y - b * x) / det)
