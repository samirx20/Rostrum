"""The frame's maths, the same as the engine's (engine/render/src/frame/mod.rs; apps/2d/FRAME.md › The maths), for
the look tools that place layers from the document without drawing (mcp/geometry.py) and for edits made in the
world view. Matrices are (a, b, c, d, e, f): a point (x, y) goes to (a·x + c·y + e, b·x + d·y + f), y down, turns
clockwise.

O = the output centre (width / 2, height / 2), H = home, F = the frame's centre, z = zoom, s = 1 / (1 + depth):

    export:  out(p)   = O + R(−roll) · zˢ · (p − H − s · (F − H))
    world:   world(p) = F + z^(s−1) · (p − H − s · (F − H))            (pinned: F + R(roll) · z⁻¹ · (q − O))
"""
from __future__ import annotations

import math
from typing import NamedTuple

from .. import fields as F
from ..evaluate import value_at
from . import TYPE

ID = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


class Shot(NamedTuple):
    """The frame at one time: its centre (x, y), zoom, roll (degrees) and home (hx, hy)."""
    x: float
    y: float
    zoom: float
    roll: float
    hx: float
    hy: float


def of(comp: dict) -> dict | None:
    """The composition's frame (a document item or a scene node), or None (a scene made before frames)."""
    return next((l for l in comp.get("layers", []) if l["type"] == TYPE), None)


def centre(comp: dict) -> tuple[float, float]:
    """O: the output's centre."""
    d = F.defaults("comp")
    p = comp.get("props", comp)
    return p.get("width", d["width"]) / 2, p.get("height", d["height"]) / 2


def shot(comp: dict, t: float, at=value_at) -> Shot | None:
    """The frame at t, or None when the composition has none. `at(layer, field, t)` reads a field: the document's
    layers by default; the Lottie export passes the scene's. A frame riding a path is where the ride puts it."""
    from ..follow import ride      # follow imports the field tables, which import this package
    frame = of(comp)
    if frame is None:
        return None
    got = {f: float(at(frame, f, t)) for f in ("x", "y", "zoom", "rotation", "homeX", "homeY")}
    got.update(ride(frame, comp["layers"], t, at) or {})
    return Shot(got["x"], got["y"], got["zoom"], got["rotation"], got["homeX"], got["homeY"])


def parts(o: tuple[float, float], cam: Shot | None, depth: float) -> tuple[float, float, float, float]:
    """The frame's matrix for a layer at `depth` as a transform: (px, py, scale, turn). The world point (px, py) lands
    on the output centre O, scaled by `scale` and turned by `turn` degrees (clockwise) about it. At home: (O, 1, 0)."""
    if cam is None:
        return o[0], o[1], 1.0, 0.0
    s = 1 / (1 + depth)
    return cam.hx + s * (cam.x - cam.hx), cam.hy + s * (cam.y - cam.hy), cam.zoom ** s, -cam.roll


def _matrix(o, px, py, z, turn) -> tuple:
    """p ↦ o + R(turn) · z · (p − (px, py))."""
    r = math.radians(turn)
    cos, sin = math.cos(r) * z, math.sin(r) * z
    return (cos, sin, -sin, cos, o[0] - cos * px + sin * py, o[1] - sin * px - cos * py)


def layer_matrix(comp: dict, cam: Shot | None, props: dict) -> tuple:
    """Where a top-level layer's world px land in the export, for the frame `cam` (from `shot`) and the layer's values
    at the time. A pinned layer (screenLock) is in the frame's own px already: the identity."""
    if cam is None or props.get("screenLock"):
        return ID
    o = centre(comp)
    return _matrix(o, *parts(o, cam, props.get("depth", 0.0)))


def world_matrix(comp: dict, cam: Shot | None, props: dict) -> tuple:
    """Where a top-level layer's own px are drawn in the world view: as the frame sees it, carried back into world
    px through the plain frame (depth 0). Depth 0 and a frame at home: the identity. Pinned: turned and sized with
    the frame's box."""
    if cam is None:
        return ID
    o = centre(comp)
    if props.get("screenLock"):
        return _matrix((cam.x, cam.y), o[0], o[1], 1 / cam.zoom, cam.roll)
    px, py, z, _ = parts(o, cam, props.get("depth", 0.0))
    return _matrix((cam.x, cam.y), px, py, z / cam.zoom, 0.0)


def undo(m, x: float, y: float) -> tuple[float, float]:
    """A point back through the inverse of the matrix `m`: an export or world point to the layer's own world px (the
    engine's `bones` reply gives each rig's matrix as `frame`)."""
    a, b, c, d, e, f = m
    det = a * d - b * c
    x, y = x - e, y - f
    return ((d * x - c * y) / det, (a * y - b * x) / det)


def leaves_home(frame: dict | None, comp: dict) -> bool:
    """Whether the frame ever shows anything but every layer as placed (a key on its move, a ride, a still value away
    from home, or home away from the output centre): the engine's wrapper rule, decided once per scene."""
    if frame is None:
        return False
    g = (lambda f: frame.get("props", frame).get(f, F.param(TYPE, f).default))
    keyed = {k.get("prop") for k in frame.get("keys", [])} | set(frame.get("anim", {}))
    return (bool(keyed & {"x", "y", "zoom", "rotation"}) or bool(g("ridePath"))
            or (g("x"), g("y"), g("zoom"), g("rotation")) != (g("homeX"), g("homeY"), 1.0, 0.0)
            or (g("homeX"), g("homeY")) != centre(comp))
