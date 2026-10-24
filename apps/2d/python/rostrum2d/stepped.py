"""Stepped timing ("on twos", "on threes"): an evaluation setting on a composition, group or layer, never baked into
the document's keys. A layer set to "As its group" (the default) takes its group's setting, a group its own group's,
up to the composition's (default every frame). Effects, masks and a rig's bones follow their layer.

Into the scene (scene.py, as each node is built: `step_of` passed down, `held`): every animated field of a stepped item is sent as `hold` keys, one every n frames from 0
to the composition's length, each holding the value the field has on that frame (its own keys, or the per-frame keys
of an expression or an auto layout). The engine draws plain keys and never sees the setting; the person's keys stay
as they are, so turning it back to every frame gives the smooth motion back. A path's shape and width profile (text
keys, `d`) are not stepped (their blends are the engine's own); a video's frames and a drawing's held frames are not changed.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.keys import track_value

FIELD = "timing"
ON = {"1": "Every frame", "2": "Every 2nd frame", "3": "Every 3rd frame", "4": "Every 4th frame"}   # "on twos", "on threes"
COMP = [Param.choice(FIELD, list(ON), label="Animate on", group="Timing", default="1", importance="secondary", labels=ON,
                     help="Hold each pose for this many frames, as hand-drawn animation does (on twos, on threes); the keys don't change")]
LAYER = [Param.choice(FIELD, ["group", *ON], label="Animate on", group="Timing", default="group", importance="secondary",
                      labels={"group": "Same as its group", **ON},
                      help="Hold each pose for this many frames; “Same as its group” takes the group's or the scene's setting")]


def option_words(rows: list[dict], in_group: bool) -> list[dict]:
    """A layer straight in a scene takes the scene's setting: its "Same as its group" reads "Same as the scene" there."""
    if in_group:
        return rows
    same = [{**o, "label": "Same as the scene"} if o["value"] == "group" else o for o in next((r["options"] for r in rows if r.get("id") == FIELD), [])]
    return [{**r, "options": same} if r.get("id") == FIELD and r.get("row") == "param" else r for r in rows]


def step_of(item: dict, n: int | None) -> int:
    """Every how many frames `item` holds a pose: its own setting, or `n` (its group's) for "As its group"; at the
    composition (`n` None) its own, every frame by default. Effects, masks, bones and nodes made in the scene (no
    setting of their own) take their layer's."""
    own = item.get(FIELD, "group" if n else "1")
    return n if own == "group" else int(own)


def held(anim: dict, n: int, duration: float, fps: float) -> dict:
    """A node's animated fields held every n frames (a path's shape keys, `d`, as they are)."""
    return {prop: keys if "d" in keys[0] else hold(keys, n, duration, fps) for prop, keys in anim.items()}


def hold(keys: list[dict], n: int, duration: float, fps: float) -> list[dict]:
    """One `hold` key every n frames with the track's value on that frame; a track that never changes stays one key."""
    if len(keys) < 2:
        return keys
    field = next(f for f in ("v", "c") if f in keys[0])
    count = math.ceil(duration * fps / n - 1e-9) + 1
    out = [{"t": k * n / fps, field: track_value(keys, k * n / fps), "ease": "hold"} for k in range(count)]
    return out if any(o[field] != out[0][field] for o in out) else out[:1]
