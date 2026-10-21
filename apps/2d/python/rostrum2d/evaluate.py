"""2D's side of the animation model: what a field is at time t, falling back to the item's own value and then
the 2D field default. The key evaluator and easing table are shared: rostrum_core.keys."""
from __future__ import annotations

from rostrum_core.keys import animated, keys_of, track_value

from . import fields as F


def value_at(owner: dict, prop: str, t: float):
    keys = keys_of(owner, prop)
    if keys:
        return track_value(keys, t)
    if prop in owner:
        return owner[prop]
    p = F.param(owner["type"], prop)
    if p is None:
        raise KeyError(f'{owner["type"]} has no field "{prop}"')
    return p.default


def resolve(owner: dict, t: float) -> dict:
    """Every field of an item at time t (still values, defaults filled in, animated ones evaluated)."""
    out = {p.name: owner.get(p.name, p.default) for p in F.FIELDS[owner["type"]]}
    for prop in animated(owner):
        out[prop] = track_value(keys_of(owner, prop), t)
    return out
