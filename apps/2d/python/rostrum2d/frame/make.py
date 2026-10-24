"""A scene's frame when the scene is made (comp.add, a script's comp(), an older file converted): at home, still,
home at the output's centre. Its id is "frame" when no other item has it (the first scene's), else
"<scene id>-frame": ids are one per document, and the frame is found by its type, never by its id (view.of).
`resized`: what a new size does to the frame and the pinned layers."""
from __future__ import annotations

from rostrum_core import ids

from .. import fields as F
from . import TYPE


def frame_id(comp_id: str, taken) -> str:
    for id_ in ("frame", f"{comp_id}-frame"):
        if id_ not in taken:
            return id_
    return ids.counted(taken, f"{comp_id}-frame")


def new(comp: dict, taken) -> dict:
    """The frame for `comp` (its width and height, defaults filled in), with an id not in `taken`."""
    d = F.defaults("comp")
    hx, hy = comp.get("width", d["width"]) / 2, comp.get("height", d["height"]) / 2
    return {"id": frame_id(comp["id"], taken), "type": TYPE, "name": F.LABELS[TYPE], **F.defaults(TYPE),
            "x": hx, "y": hy, "homeX": hx, "homeY": hy, "keys": [], "exprs": []}


def resized(ctx, comp_id: str, before: tuple[float, float]):
    """After a scene's size changed from `before` (comp.set and comp.size, the only writes of a scene's size): the
    frame takes the new size about its centre, so it keeps looking at the same world point, and its zoom, turn, keys
    and home are untouched (depth layers keep their parallax). Layers in the world don't move. Pinned layers (in the
    frame's own px) shift by half the change, still values and keys, so they keep their distance from the frame's
    centre: a centred title stays centred (FRAME.md › Changing the size)."""
    from . import place, view
    comp = ctx.item(comp_id)
    if comp.get("type") != "comp":
        return
    cx, cy = view.centre(comp)
    dx, dy = cx - before[0] / 2, cy - before[1] / 2
    if dx == 0 and dy == 0:
        return
    for layer in comp.get("layers", []):
        if layer.get("screenLock") and layer.get("type") != TYPE:
            place.carry(ctx, layer["id"], (1.0, 0.0, 0.0, 1.0, dx, dy))
