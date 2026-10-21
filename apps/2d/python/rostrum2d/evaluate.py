"""The one animation model: a field is either still (its value on the item) or animated (it has keys; then the
keys alone decide its value and the item's own value is ignored). Between two keys the first key's ease shapes
the way; before the first key and after the last the value holds. Colours travel in linear light.

This is the reference the Rust engine implements (ENGINE_CONTRACT.md › Evaluation; checked by the engine's
scene tests); Python uses it for the inspector's "value now" and the motion facts. Frames are drawn by the engine only.
"""
from __future__ import annotations

from . import fields as F
from .easing import ease


def keys_of(owner: dict, prop: str) -> list[dict]:
    return sorted((k for k in owner.get("keys", []) if k.get("prop") == prop), key=lambda k: k["t"])


def animated(owner: dict) -> set[str]:
    return {k["prop"] for k in owner.get("keys", [])}


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _srgb(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def mix_color(a: str, b: str, p: float) -> str:
    ca = [_lin(int(a[i:i + 2], 16) / 255) for i in (1, 3, 5)]
    cb = [_lin(int(b[i:i + 2], 16) / 255) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(_srgb(x + (y - x) * p) * 255):02x}" for x, y in zip(ca, cb))


def track_value(keys: list[dict], t: float):
    """The value of a sorted, non-empty list of keys at time t."""
    field = "c" if "c" in keys[0] else "v"
    if t <= keys[0]["t"]:
        return keys[0][field]
    for k0, k1 in zip(keys, keys[1:]):
        if t < k1["t"]:
            p = ease(k0, (t - k0["t"]) / (k1["t"] - k0["t"]))
            if field == "c":
                return mix_color(k0["c"], k1["c"], min(1.0, max(0.0, p)))
            return k0["v"] + (k1["v"] - k0["v"]) * p
    return keys[-1][field]


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
