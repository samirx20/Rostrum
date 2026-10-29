"""Where a script's items are, for calls that write keys from one section to the next (script_transitions.py): the
chain of groups an item sits in, its fields at a time, and points between a group's own px and the scene's px. Reads
the tree the script has built so far; writes nothing. Groups are taken as x / y / anchor / scale / Stretch / rotation
(tilt is left out). No Qt."""
from __future__ import annotations

import math

from . import script_time as T
from .evaluate import resolve


def path_to(build, ref, where: str) -> list[dict]:
    """[scene, group …, item] for an item this script made (an Item or its id)."""
    id_ = getattr(ref, "id", ref)

    def walk(node, path):
        for c in node.get("layers", []):
            if c.get("id") == id_:
                return path + [c]
            got = walk(c, path + [c])
            if got:
                return got
        return None
    for comp in build.root["comps"]:
        got = walk(comp, [comp])
        if got:
            return got
    raise ValueError(f'{where}: no layer or group "{id_}" was made earlier in this script; give a group or layer it made '
                     "(the handle group(…) gave, or its id)")


def values(build, node: dict, t: float) -> dict:
    """Every field of `node` at `t` seconds (keys on a marker read as their seconds)."""
    keys = [{**k, "t": T.seconds(build, k["t"], node["id"])} if isinstance(k["t"], str) else k for k in node.get("keys", [])]
    return resolve({**node, "keys": keys}, t)


def _step(v: dict, p, inverse=False):
    """A point between a group's own px and its parent's px (inverse: parent -> own)."""
    sx, sy = v["scale"] * v.get("scaleX", 1.0), v["scale"] * v.get("scaleY", 1.0)
    ax, ay = v["anchorX"] * v.get("w", 0.0), v["anchorY"] * v.get("h", 0.0)
    a = math.radians(v["rotation"])
    c, s = math.cos(a), math.sin(a)
    if not inverse:
        x, y = (p[0] - ax) * sx, (p[1] - ay) * sy
        return v["x"] + x * c - y * s, v["y"] + x * s + y * c
    x, y = p[0] - v["x"], p[1] - v["y"]
    x, y = x * c + y * s, -x * s + y * c
    return x / (sx or 1e-9) + ax, y / (sy or 1e-9) + ay


def to_scene(build, groups: list[dict], p, t: float):
    """A point in the innermost group's px -> scene px (groups: outermost first)."""
    for g in reversed(groups):
        p = _step(values(build, g, t), p)
    return p


def from_scene(build, groups: list[dict], p, t: float):
    """A point in scene px -> the innermost group's px."""
    for g in groups:
        p = _step(values(build, g, t), p, inverse=True)
    return p


def product(build, groups: list[dict], field: str, t: float) -> float:
    out = 1.0
    for g in groups:
        out *= values(build, g, t)[field]
    return out


def view(build, comp: dict, t: float) -> tuple[float, float, float, float]:
    """The frame's view at `t` in scene px: (left, top, width, height) (its rotation is left out)."""
    cam = next((c for c in comp["layers"] if c["type"] == "camera"), None)
    v = values(build, cam, t) if cam else {"x": comp["width"] / 2, "y": comp["height"] / 2, "zoom": 1.0}
    w, h = comp["width"] / v["zoom"], comp["height"] / v["zoom"]
    return v["x"] - w / 2, v["y"] - h / 2, w, h
