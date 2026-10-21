"""Where each layer sits on the canvas at a time, in composition pixels: the selection outline and click-to-pick.
No Qt.

A layer's box: its anchor sits at (x, y) inside its parent (a group's layers are placed from the group's top-left
corner); the box is w x h times scale, turned by `rot` degrees about the anchor (the selection outline turns with it;
picking turns the pointer back the same way). A group's turn is not passed on to its layers; tilt is not taken into account.
A layer's size is rostrum2d/sizes.py's (a text's is the engine's laid-out box, rostrum2d/textsize.py, on a path too).
A layer in an auto layout is where the layout puts it (rostrum2d/layout.py).
"""
from __future__ import annotations

import math

from rostrum2d import fields as F
from rostrum2d.evaluate import resolve
from rostrum2d.layout import solve
from rostrum2d.sizes import own_size


def boxes(comp: dict, t: float) -> list[dict]:
    """[{id, x, y, w, h}] for every layer showing at t, bottom of the stack first (a group before its layers)."""
    out: list[dict] = []
    placed = solve(comp, t)                 # where auto layouts put their layers (rostrum2d/layout.py)

    def walk(layers, ox, oy):
        for lay in layers:
            if lay["type"] == "camera":         # not drawn: no box (and no scale)
                continue
            p = {**resolve(lay, t), **placed.get(lay["id"], {})}
            if not (p["start"] <= t < p["end"]):
                continue
            w, h = own_size(lay["type"], p)
            sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
            left = ox + p["x"] - p["anchorX"] * w * sx
            top = oy + p["y"] - p["anchorY"] * h * sy
            out.append({"id": lay["id"], "type": lay["type"], "x": left, "y": top, "w": w * sx, "h": h * sy,
                        "rot": p["rotation"], "ax": p["anchorX"], "ay": p["anchorY"]})
            if lay["type"] == "group":
                walk(lay.get("layers", []), left, top)

    walk(comp.get("layers", []), 0.0, 0.0)
    return out


def corners(b: dict) -> list[tuple[float, float]]:
    """The four corners of a box (turned about its anchor), composition px."""
    c, s = math.cos(math.radians(b["rot"])), math.sin(math.radians(b["rot"]))
    ox, oy = b["x"] + b["ax"] * b["w"], b["y"] + b["ay"] * b["h"]
    return [(ox + c * (px - ox) - s * (py - oy), oy + s * (px - ox) + c * (py - oy))
            for px, py in ((b["x"], b["y"]), (b["x"] + b["w"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]), (b["x"], b["y"] + b["h"]))]


def extent(b: dict) -> tuple[float, float, float, float]:
    """x0, y0, x1, y1 of the box's corners."""
    xs, ys = zip(*corners(b))
    return min(xs), min(ys), max(xs), max(ys)


def inside(b: dict, x: float, y: float) -> bool:
    c, s = math.cos(math.radians(-b["rot"])), math.sin(math.radians(-b["rot"]))
    ox, oy = b["x"] + b["ax"] * b["w"], b["y"] + b["ay"] * b["h"]
    lx, ly = ox + c * (x - ox) - s * (y - oy), oy + s * (x - ox) + c * (y - oy)
    return b["x"] <= lx <= b["x"] + b["w"] and b["y"] <= ly <= b["y"] + b["h"]


def pick(comp: dict, t: float, x: float, y: float) -> str:
    """The topmost layer under (x, y), or "" (groups count only where none of their layers is)."""
    hits = [b for b in boxes(comp, t) if inside(b, x, y)]
    return hits[-1]["id"] if hits else ""


def layer_of(doc, item_id: str) -> str:
    """The layer an effect, mask or key belongs to (itself for a layer); "" for a composition."""
    while item_id and doc.item(item_id)["type"] not in F.LAYERS:
        if doc.item(item_id)["type"] == "comp":
            return ""
        item_id = doc.parent_of(item_id)[0]
    return item_id
