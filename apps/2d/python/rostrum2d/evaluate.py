"""2D's side of the animation model: what a field is at time t, falling back to the item's own value and then
the 2D field default. The key evaluator and easing table are shared: rostrum_core.keys."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from rostrum_core.keys import animated, keys_of, layers, track_value
from rostrum_core.marker_times import seconds

from . import fields as F, widthprofile

_MARKS: ContextVar = ContextVar("rostrum2d_script_marks", default=None)


@contextmanager
def script_marks(times):
    """While a script runs, its own reads (a group's fit, a layout, tap, measure(at=) ...) see keys timed on a marker
    ("#s2+0.7") at that marker's moment: `times()` gives the markers in force ({name: seconds}, the project's and the
    ones the script made so far). A script counts every time in composition seconds, so the key's seconds are the
    marker's plus the offset. Outside a script the app places marker keys first (retime.py)."""
    token = _MARKS.set(times)
    try:
        yield
    finally:
        _MARKS.reset(token)


def placed(keys: list[dict]) -> list[dict]:
    """`keys` with marker times as composition seconds while a script runs (script_marks), sorted; as is otherwise.
    A marker that isn't there fails naming the key and the markers that exist."""
    marks = _MARKS.get()
    if marks is None or not any(isinstance(k["t"], str) for k in keys):
        return keys
    now = marks()
    out = [{**k, "t": seconds(k["t"], now, k.get("id", "key"))} if isinstance(k["t"], str) else k for k in keys]
    return sorted(out, key=lambda k: k["t"])


def _track(prop: str, keys: list[dict], t: float):
    """A track's value at t: shared evaluation, but a width profile blends here (the engine's rule, widthprofile.py)."""
    keys = placed(keys)
    return widthprofile.track(keys, t) if prop == "widthProfile" else track_value(keys, t)


def value_at(owner: dict, prop: str, t: float):
    keys = keys_of(owner, prop)
    if keys:
        return _track(prop, keys, t)
    if prop in owner:
        return owner[prop]
    p = F.param(owner["type"], prop)
    if p is None:
        raise KeyError(f'{owner["type"]} has no field "{prop}"')
    return p.default


def resolve(owner: dict, t: float, stack: list[dict] = ()) -> dict:
    """Every field of an item at time t (still values, defaults filled in, animated ones evaluated). `stack`: the
    document's animation layers (rostrum_core.keys.layers.stack_of), laid over the Base as the engine is sent them
    (layerbake.py); left out, the Base alone."""
    out = {p.name: owner.get(p.name, p.default) for p in F.FIELDS[owner["type"]]}
    for prop in animated(owner):
        if keys := keys_of(owner, prop):                # a field keyed only on an animation layer keeps its Base still
            out[prop] = _track(prop, keys, t)
        if stack and prop in out and F.key_field(owner["type"], prop) != "d":
            out[prop] = layers.value(owner, prop, t, stack, out[prop], lambda ks, at: track_value(placed(ks), at))
    return out
