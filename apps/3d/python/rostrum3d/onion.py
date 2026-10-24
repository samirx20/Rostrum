"""Onion skin: which ghosts to draw for an item at a frame, as the core's `view` request takes them
(ENGINE_CONTRACT.md § 4 `ghosts`). One answer for the viewport (screen3d/onion_qt.py) and agents (mcp look_frame
`onion`): the item at its previous and next keys ("keys"), or 2 and 4 frames before and after ("frames"); before
tinted red, after green, as 2D's onion skin. Times are document seconds, frames whole shot frames.
"""
from __future__ import annotations

from rostrum_core.tree import walk

from . import fields as F

MODES = ("keys", "frames")
BEFORE, AFTER = [0.85, 0.22, 0.18], [0.2, 0.8, 0.32]     # linear RGB
OPACITY = {1: 0.4, 2: 0.22}                               # nearest ghost, the one past it


def key_frames(item: dict, fps: float) -> list[int]:
    """The frames of every key on the item and on everything inside it, in order."""
    times = {round(k["t"] * fps) for k in walk(item, F.LISTS) if k.get("type") == "key"}
    return sorted(times)


def ghosts(item: dict, frame: int, info: dict, mode: str = "keys") -> list[dict]:
    """The ghosts of `item` seen at `frame` of a shot (`info`: compile.shot_info), nearest first each way."""
    if mode not in MODES:
        raise ValueError(f'onion skin: mode "{mode}" is not one of {", ".join(MODES)}')
    lo, hi = info["start"], info["end"]
    if mode == "keys":
        keys = [f for f in key_frames(item, info["fps"]) if lo <= f <= hi]
        before = [f for f in keys if f < frame][-1:]
        after = [f for f in keys if f > frame][:1]
    else:
        before = [f for f in (frame - 2, frame - 4) if f >= lo]
        after = [f for f in (frame + 2, frame + 4) if f <= hi]
    out = []
    for frames, tint in ((before, BEFORE), (after, AFTER)):
        for n, f in enumerate(frames, 1):
            out.append({"frame": f, "items": [item["id"]], "tint": tint, "opacity": OPACITY[n]})
    return out
