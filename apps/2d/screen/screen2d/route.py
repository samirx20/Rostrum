"""2D's side of the one animation model on screen (the shared rules: rostrum_gui.route): what keys may drive, what
the inspector shows (values at the playhead, evaluate.resolve), and that an expression-driven field has no key mark.
No Qt.
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d.evaluate import resolve, value_at
from rostrum_gui.route import KeyRoute

from . import exprs


def drives(item: dict, prop: str) -> bool:
    """Keys may drive this field of this item."""
    return item["type"] in F.ANIMATED_OWNERS and prop in F.animatable(item["type"])


def shown_values(item: dict, t: float) -> dict:
    if item["type"] in F.ANIMATED_OWNERS:
        return {**item, **resolve(item, t)}
    return item


_route = KeyRoute(F, drives, value_at, exprs.drives)
value_call, edit_call, anim_state, animate_calls = _route.value_call, _route.edit_call, _route.anim_state, _route.animate_calls
