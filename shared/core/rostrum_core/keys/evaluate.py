"""The one animation model: a field is either still (its value on the item) or animated (it has keys; then the
keys alone decide its value and the item's own value is ignored). Between two keys the first key's ease shapes
the way; before the first key the value holds, and after the last too unless the last key says otherwise (after.py). Colours travel in linear light.

This is the reference the Rust engine implements (ENGINE_CONTRACT.md › Evaluation; checked by the engine's
scene tests); Python uses it for the inspector's "value now" and the motion facts. Frames are drawn by the engine only.
What is app-specific (a field's default when it has no keys: `value_at`, `resolve`) lives in each app.
"""
from __future__ import annotations

from .after import after_of, extend
from .easing import ease
from .marked import order


def keys_of(owner: dict, prop: str) -> list[dict]:
    """A field's keys by time. Keys timed on a marker (marked.py) sort after the others until the app resolved
    them; `track_value` needs resolved keys (seconds only)."""
    return sorted((k for k in owner.get("keys", []) if k.get("prop") == prop), key=lambda k: order(k["t"]))


def animated(owner: dict) -> set[str]:
    return {k["prop"] for k in owner.get("keys", [])}


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _srgb(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _alpha(c: str) -> float:
    return int(c[7:9], 16) / 255 if len(c) == 9 else 1.0


def mix_color(a: str, b: str, p: float) -> str:
    """Two `#rrggbb` / `#rrggbbaa` colours mixed in linear light, alpha straight; written `#rrggbbaa` only while the
    result is see-through (the same as the engine's `mix`)."""
    ca = [_lin(int(a[i:i + 2], 16) / 255) for i in (1, 3, 5)]
    cb = [_lin(int(b[i:i + 2], 16) / 255) for i in (1, 3, 5)]
    out = "#" + "".join(f"{round(_srgb(x + (y - x) * p) * 255):02x}" for x, y in zip(ca, cb))
    alpha = round(min(1.0, max(0.0, _alpha(a) + (_alpha(b) - _alpha(a)) * p)) * 255)
    return out if alpha == 255 else out + f"{alpha:02x}"


def key_value(key: dict):
    """A key's value, whichever kind it holds (v, c or d)."""
    return next(key[f] for f in ("v", "c", "d") if f in key)


def track_value(keys: list[dict], t: float):
    """The value of a sorted, non-empty list of keys at time t. A path's shape (`d`) is morphed by the engine only;
    here it reads as the shape of the key that starts the stretch."""
    if any(isinstance(k["t"], str) for k in keys):     # never a silent wrong value: place them first (marked.py)
        raise ValueError(f'key {next(k for k in keys if isinstance(k["t"], str)).get("id", "")} is timed on a marker '
                         "and was not placed: the app resolves marker keys (keys.marked.resolve) before evaluating")
    if after_of(keys) != "stay":                       # repeat, back and forth, carry on: written out as keys (after.py)
        keys = extend(keys, t)
    field = next(f for f in ("v", "c", "d") if f in keys[0])
    if t <= keys[0]["t"]:
        return keys[0][field]
    for k0, k1 in zip(keys, keys[1:]):
        if t < k1["t"]:
            p = ease(k0, (t - k0["t"]) / (k1["t"] - k0["t"]))
            if field == "d":
                return k0["d"]
            if field == "c":
                return mix_color(k0["c"], k1["c"], min(1.0, max(0.0, p)))
            return k0["v"] + (k1["v"] - k0["v"]) * p
    return keys[-1][field]
