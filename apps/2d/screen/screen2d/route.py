"""2D's side of the one animation model on screen (the shared rules: rostrum_gui.route): what keys may drive, what
the inspector shows (values at the playhead, evaluate.resolve), and that an expression-driven field has no key mark.
No Qt.
"""
from __future__ import annotations

from functools import lru_cache

from rostrum2d import fields as F
from rostrum2d.evaluate import resolve, value_at
from rostrum_core.keys import keys_of, marked
from rostrum_gui.route import KeyRoute

from . import exprs


def drives(item: dict, prop: str) -> bool:
    """Keys may drive this field of this item."""
    return item["type"] in F.ANIMATED_OWNERS and prop in _animatable(item["type"])


@lru_cache(maxsize=None)
def _animatable(kind: str) -> frozenset:
    """F.animatable, once per kind: the panel asks it for every row on every refresh."""
    return frozenset(F.animatable(kind))


def shown_values(item: dict, t: float) -> dict:
    if item["type"] in F.ANIMATED_OWNERS:
        return {**item, **resolve(item, t)}
    return item


class Route2D(KeyRoute):
    """A key of the field timed on a shared marker and sitting at the playhead is THE key there: an edit changes it
    and it stays on its marker (key.add at its written time), never a second key at the playhead's seconds beside it.
    Where keys sit in time needs the open screen's placement (`use`); without one (a script) the plain rule holds."""

    def value_call(self, item: dict, prop: str, value, t: float) -> dict:
        call = super().value_call(item, prop, value, t)
        written = _marked_at(item, prop, t)
        if written is not None:
            args = {k: v for k, v in call["args"].items() if k != "at"}
            call = {"op": "key.add", "target": call["target"], "args": {**args, "t": written}}
        return call


_screen = [None]       # (placed_item(id), offset(id), fps()) of the open screen (bridge2d.py)


def use(placed_item, offset, fps) -> tuple:
    """Where items' keys sit in the open screen's composition seconds; returns the handle `drop` takes."""
    _screen[0] = (placed_item, offset, fps)
    return _screen[0]


def drop(handle) -> None:
    """The screen closing: forgotten, unless another screen took over since."""
    if _screen[0] is handle:
        _screen[0] = None


def _marked_at(item: dict, prop: str, t: float):
    """The written time ("#drop+0.2") of the field's marker key within half a frame of `t` (the item's own seconds)."""
    if _screen[0] is None or not any(marked.marked(k) for k in keys_of(item, prop)):
        return None
    placed_item, offset, fps = _screen[0]
    at, half = t + offset(item["id"]), 0.5 / (fps() or 30)
    return next((k["ref"] for k in keys_of(placed_item(item["id"]), prop) if "ref" in k and abs(k["t"] - at) < half), None)


_route = Route2D(F, drives, value_at, exprs.drives)
value_call, edit_call, anim_state, animate_calls = _route.value_call, _route.edit_call, _route.anim_state, _route.animate_calls
