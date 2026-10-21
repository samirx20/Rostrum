"""Where each layer sits on the canvas at a time, in composition pixels: the selection outline and click-to-pick.
No Qt.

A layer's box: its anchor sits at (x, y) inside its parent (a group's layers are placed from the group's top-left
corner); the box is w x h times scale. Rotation and tilt are not taken into account yet (the box stays upright).
A text has no size in the document, so its box is an ESTIMATE from size, line height and character count, until
the engine reports laid-out boxes. A text on a path has the engine's box for it: from its origin to the path's far
corner (scene/letters.rs `Placed`).
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d import pathdata
from rostrum2d.evaluate import resolve

TEXT_ADVANCE = 0.55        # average character width per px of font size (estimate)


def size_of(layer: dict, p: dict) -> tuple[float, float]:
    if layer["type"] != "text":
        return p["w"], p["h"]
    if p.get("path"):
        _, _, x1, y1 = pathdata.bounds(pathdata.commands(p["path"]))
        return max(x1, 0.0), max(y1, 0.0)
    lines = str(p["body"]).split("\n") or [""]
    w = p["boxWidth"] or max(len(line) for line in lines) * p["size"] * TEXT_ADVANCE
    return w, len(lines) * p["size"] * p["lineHeight"]


def boxes(comp: dict, t: float) -> list[dict]:
    """[{id, x, y, w, h}] for every layer showing at t, bottom of the stack first (a group before its layers)."""
    out: list[dict] = []

    def walk(layers, ox, oy):
        for lay in layers:
            p = resolve(lay, t)
            if not (p["start"] <= t < p["end"]):
                continue
            w, h = size_of(lay, p)
            sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
            left = ox + p["x"] - p["anchorX"] * w * sx
            top = oy + p["y"] - p["anchorY"] * h * sy
            out.append({"id": lay["id"], "x": left, "y": top, "w": w * sx, "h": h * sy})
            if lay["type"] == "group":
                walk(lay.get("layers", []), left, top)

    walk(comp.get("layers", []), 0.0, 0.0)
    return out


def pick(comp: dict, t: float, x: float, y: float) -> str:
    """The topmost layer under (x, y), or "" (groups count only where none of their layers is)."""
    hits = [b for b in boxes(comp, t) if b["x"] <= x <= b["x"] + b["w"] and b["y"] <= y <= b["y"] + b["h"]]
    return hits[-1]["id"] if hits else ""


def layer_of(doc, item_id: str) -> str:
    """The layer an effect, mask or key belongs to (itself for a layer); "" for a composition."""
    while item_id and doc.item(item_id)["type"] not in F.LAYERS:
        if doc.item(item_id)["type"] == "comp":
            return ""
        item_id = doc.parent_of(item_id)[0]
    return item_id
