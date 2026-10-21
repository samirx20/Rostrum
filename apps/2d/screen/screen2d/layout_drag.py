"""Dragging a layer that sits in an auto layout: it changes slot instead of position. The slots are the ones the
solver gives (rostrum2d/layout.py); the pointer picks the nearest, and the move is one layer.arrange call
(the same operation the layers panel uses). No Qt."""
from __future__ import annotations

import math

from rostrum2d.layout import has_layout, members

from . import bounds


def begin(doc, comp: dict, layer_id: str, t: float):
    """The grab for a layer in a laid-out group: {layer, parent, order, centres}, or None (not in a layout)."""
    parent_id = doc.parent_of(layer_id)[0]
    parent = doc.item(parent_id)
    if not has_layout(parent):
        return None
    order = [c["id"] for c in members(parent, t)]
    if layer_id not in order:
        return None
    boxes = {b["id"]: b for b in bounds.boxes(comp, t)}
    centres = {i: (boxes[i]["x"] + boxes[i]["w"] / 2, boxes[i]["y"] + boxes[i]["h"] / 2) for i in order if i in boxes}
    return {"layer": layer_id, "parent": parent_id, "order": order, "centres": centres} if layer_id in centres else None


def call(doc, grab: dict, dx: float, dy: float) -> dict:
    """layer.arrange to the slot nearest the dragged layer's centre moved by (dx, dy) composition px."""
    cx, cy = grab["centres"][grab["layer"]]
    slot = min(grab["order"], key=lambda i: math.hypot(grab["centres"][i][0] - cx - dx, grab["centres"][i][1] - cy - dy))
    layers = doc.item(grab["parent"])["layers"]
    index = next(n for n, c in enumerate(layers) if c["id"] == slot)
    return {"op": "layer.arrange", "target": [grab["layer"]], "args": {"into": grab["parent"], "index": index}}
