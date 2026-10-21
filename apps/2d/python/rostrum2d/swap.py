"""Swap sets: a group that shows one of its children at a time (mouth shapes, hands, eyes, blinks). The slot is an
ordinary group with `swap` on; `show` says which child, counting from 0 in the list, and is a stepped choice: its keys
always read as jumps (the value holds until the next key, whatever ease the key says).

Into the scene (scene.py): both fields stay on the Python side (PY_ONLY). `apply` samples `show` on every frame and
sends each child's opacity multiplied by 1 (shown) or 0 (hidden): a child with no opacity keys gets one hold key where
it turns on or off; a child with its own opacity keys gets one hold key per frame of own(t) x shown(t). The
document's keys are not changed.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.keys import keys_of, track_value

PY_ONLY: dict[str, set[str]] = {"group": {"swap", "show"}}
ON = {"is": ["swap", True]}
GROUP = [
    Param.toggle("swap", label="One at a time", group="Swap set", importance="secondary", default=False,
                 help="Show one child at a time: mouth shapes, hands, blinks"),
    Param.number("show", label="Shows", group="Swap set", min=0, max=999, step=1, integer=True, default=0,
                 importance="primary", valid_when=ON,
                 help="Which child shows: 0 = the first in the list. Its keys are a stepped choice: a jump, never a blend"),
]


def index_at(item: dict, t: float, count: int) -> int:
    """The child a swap set shows at time t: `show` (its keys held, rounded), kept inside the children."""
    keys = [{**k, "ease": "hold"} for k in keys_of(item, "show")]
    value = track_value(keys, t) if keys else item.get("show", 0)
    return max(0, min(count - 1, math.floor(value + 0.5))) if count else 0


def apply(node: dict, items: dict[str, dict], duration: float, fps: float) -> None:
    """Make the scene node tree's swap sets show one child at a time, in place."""
    item = items.get(node["id"], {})
    kids = node.get("layers", [])
    if node["type"] == "group" and item.get("swap") and kids:
        frames = math.ceil(duration * fps - 1e-9) + 1
        shown = [index_at(item, f / fps, len(kids)) for f in range(frames)]
        for i, kid in enumerate(kids):
            _gate(kid, [1.0 if s == i else 0.0 for s in shown], fps)
    for kid in kids:
        apply(kid, items, duration, fps)


def _gate(kid: dict, vis: list[float], fps: float) -> None:
    """Multiply the child's opacity by vis (one 1 or 0 per frame)."""
    own = kid.get("anim", {}).get("opacity")
    if own:
        keys = [{"t": f / fps, "v": track_value(own, f / fps) * v, "ease": "hold"} for f, v in enumerate(vis)]
    else:
        base = kid["props"].get("opacity", 1.0)
        keys = [{"t": f / fps, "v": base * v, "ease": "hold"} for f, v in enumerate(vis) if f == 0 or v != vis[f - 1]]
        if len(keys) == 1:                      # never changes: just its opacity
            kid["props"]["opacity"] = keys[0]["v"]
            return
    kid.setdefault("anim", {})["opacity"] = keys


def child_index(kids: list[str], which) -> int:
    """A child named by id or counted from 0 -> its place in the list; ValueError naming the children if it isn't one."""
    if isinstance(which, int) and not isinstance(which, bool):
        if 0 <= which < len(kids):
            return which
    elif which in kids:
        return kids.index(which)
    raise ValueError(f'"{which}" is not a child of the swap set; its children are: '
                     + (", ".join(f"{i} {k}" for i, k in enumerate(kids)) or "none yet"))
