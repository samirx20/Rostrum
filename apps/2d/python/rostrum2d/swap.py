"""Swap sets: a group that shows one of its children at a time (mouth shapes, hands, eyes, blinks). The slot is an
ordinary group with `swap` on; `show` says which child, counting from 0 in the list, and is a stepped choice: its keys
always read as jumps (the value holds until the next key, whatever ease the key says).

Into the scene (scene.py): both fields stay on the Python side (PY_ONLY). `gates` samples `show` on every frame and
gives each child its shown-or-not per frame; the child's node, as it is built, sends its opacity multiplied by 1
(shown) or 0 (hidden) (`gate`): a child with no opacity keys gets one hold key where it turns on or off; a child with
its own opacity keys gets one hold key per frame of own(t) x shown(t). The document's keys are not changed.
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


def gates(item: dict, count: int, duration: float, fps: float) -> list[tuple[float, ...]] | None:
    """A swap set's `count` children (its engine node's layers, its background first) each as 1 or 0 per frame
    (shown or not); None for anything else (not a swap set, no children)."""
    if item.get("type") != "group" or not item.get("swap") or not count:
        return None
    frames = math.ceil(duration * fps - 1e-9) + 1
    shown = [index_at(item, f / fps, count) for f in range(frames)]
    return [tuple(1.0 if s == i else 0.0 for s in shown) for i in range(count)]


def gate(kid: dict, vis: tuple[float, ...], fps: float) -> None:
    """Multiply a node being built by its swap set's vis (one 1 or 0 per frame)."""
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
