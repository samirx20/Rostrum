"""Stepped timing ("on twos", "on threes"): an evaluation setting on a composition, group or layer, never baked into
the document's keys. A layer set to "As its group" (the default) takes its group's setting, a group its own group's,
up to the composition's (default every frame). Effects, masks and a rig's bones follow their layer.

Into the scene (scene.py): every animated field of a stepped item is sent as `hold` keys, one every n frames from 0
to the composition's length, each holding the value the field has on that frame (its own keys, or the per-frame keys
of an expression or an auto layout). The engine draws plain keys and never sees the setting; the person's keys stay
as they are, so turning it back to every frame gives the smooth motion back. A path's shape (`d`) is not stepped
(its morph is the engine's own); a video's frames and a drawing's held frames are not changed.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.keys import track_value

FIELD = "timing"
ON = {"1": "Every frame", "2": "On twos", "3": "On threes", "4": "On fours"}
COMP = [Param.choice(FIELD, list(ON), label="Steps", group="Timing", default="1", importance="secondary", labels=ON,
                     help="Hold each pose for this many frames, as hand-drawn animation does; the keys don't change")]
LAYER = [Param.choice(FIELD, ["group", *ON], label="Steps", group="Timing", default="group", importance="secondary",
                      labels={"group": "As its group", **ON},
                      help="Hold each pose for this many frames; “As its group” takes the group's or composition's setting")]


def apply(node: dict, items: dict[str, dict], duration: float, fps: float, n: int | None = None) -> None:
    """Make the scene node tree `node` (the composition's) stepped where its items ask, in place. `items`: every item
    of the composition by id (the document's values, for their `timing`)."""
    own = items.get(node["id"], {}).get(FIELD, "group" if n else "1")
    n = n if own == "group" else int(own)
    if n > 1 and node.get("anim"):
        node["anim"] = {prop: keys if prop == "d" else hold(keys, n, duration, fps) for prop, keys in node["anim"].items()}
    for key in ("effects", "masks", "layers", "rig"):
        for child in node.get(key, []):
            apply(child, items, duration, fps, n)


def hold(keys: list[dict], n: int, duration: float, fps: float) -> list[dict]:
    """One `hold` key every n frames with the track's value on that frame; a track that never changes stays one key."""
    if len(keys) < 2:
        return keys
    field = next(f for f in ("v", "c") if f in keys[0])
    count = math.ceil(duration * fps / n - 1e-9) + 1
    out = [{"t": k * n / fps, field: track_value(keys, k * n / fps), "ease": "hold"} for k in range(count)]
    return out if any(o[field] != out[0][field] for o in out) else out[:1]
