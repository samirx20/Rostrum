"""A scene's frame when the scene is made (comp.add, a script's comp(), an older file converted): at home, still,
home at the output's centre. Its id is "frame" when no other item has it (the first scene's), else
"<scene id>-frame": ids are one per document, and the frame is found by its type, never by its id (view.of)."""
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
    """After a scene's size changed from `before` (comp.set, comp.size): a frame that never left home moves its centre
    and home to the new output centre, so the picture stays the scene's top-left width × height, as before frames. A
    frame that was moved or keyed keeps looking where it looked (FRAME.md › Changing the size)."""
    from . import view
    comp = ctx.item(comp_id)
    frame = view.of(comp) if comp.get("type") == "comp" else None
    if frame is None or view.centre(comp) == (before[0] / 2, before[1] / 2):
        return
    if view.leaves_home(frame, {"width": before[0], "height": before[1]}):
        return
    cx, cy = view.centre(comp)
    for field, v in (("x", cx), ("y", cy), ("homeX", cx), ("homeY", cy)):
        ctx.set(frame["id"], field, v)
