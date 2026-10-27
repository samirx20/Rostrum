"""Varied copies: `layer.duplicate` with `vary_*` ranges. Each copy gets its own small random change on top of its step:
scale (a factor), turn, move, colour (hue and lightness), opacity and the time its animation starts. The numbers come
from a generator seeded by `seed`, the original and the copy's number, so the same seed gives the same copies and a new
seed a new set. What comes out is an ordinary layer (plain values, plain keys); nothing remembers the variation.
"""
from __future__ import annotations

import colorsys
import random
import re

from rostrum_core import Param

from . import fields as F

HEX = re.compile(r"^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$")
RANGES = ("vary_scale", "vary_turn", "vary_move", "vary_hue", "vary_light", "vary_opacity", "vary_time")


def _r(name, label, unit, hi, help):
    return Param.number(name, label=label, unit=unit, min=0, max=hi, importance="deep", help=help)


PARAMS = [
    Param.number("seed", label="Variation seed", min=0, max=10**9, integer=True, importance="deep",
                 help="With any vary_ range: the same seed gives the same copies, another seed another set (default 1)"),
    _r("vary_scale", "Vary scale", "±", 0.95, "Each copy's scale times a random factor between 1 - this and 1 + this (0.25 = from 75 % to 125 %)"),
    _r("vary_turn", "Vary turn", "± °", 360, "Each copy turned a random amount up to this many degrees either way"),
    _r("vary_move", "Vary position", "± px", 100000, "Each copy moved a random amount up to this many px on x and on y"),
    _r("vary_hue", "Vary hue", "± °", 180, "Colour fields (fill, stroke …) turned round the colour wheel by up to this many degrees; the same turn for all colours of one copy"),
    _r("vary_light", "Vary lightness", "±", 1, "Colour fields made lighter or darker by up to this much (0.2 = up to 20 points of lightness)"),
    _r("vary_opacity", "Vary opacity", "±", 1, "Opacity changed by up to this much either way (kept between 0 and 1)"),
    _r("vary_time", "Vary timing", "± s", 3600, "The copy's animation starts earlier or later by up to this many seconds (its keys shift together; none before 0 s)"),
]


def wanted(args: dict) -> dict:
    """The ranges given, as {name: amount}; a seed with no range is a mistake caught by the caller."""
    return {k: float(args[k]) for k in RANGES if args.get(k)}


def _shift_colour(value, hue: float, light: float):
    m = HEX.match(value) if isinstance(value, str) else None
    if not m:
        return value
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb((h + hue / 360) % 1.0, min(1.0, max(0.0, l + light)), s)
    return "#" + "".join(f"{round(c * 255):02x}" for c in (r, g, b)) + (m.group(2) or "")


def _colour_fields(type_: str) -> set[str]:
    return {p.name for p in F.FIELDS.get(type_, ()) if p.type == "color"}


def draw(ranges: dict, seed: int, key: str) -> dict:
    """One copy's random amounts (the same for the same seed and key): what `vary` then applies to the copy and its keys."""
    rng = random.Random(f"{seed}|{key}")
    u = lambda name: rng.uniform(-ranges[name], ranges[name]) if name in ranges else 0.0     # noqa: E731
    return {"scale": 1 + u("vary_scale"), "turn": u("vary_turn"), "dx": u("vary_move"), "dy": u("vary_move"),
            "hue": u("vary_hue"), "light": u("vary_light"), "opacity": u("vary_opacity"), "time": u("vary_time")}


def vary(item: dict, d: dict) -> dict:
    """`item` (a copy the caller owns) or one of its keys changed by the amounts `d` (draw)."""
    if item.get("type") == "key":
        return _vary_key(item, d)
    cols = _colour_fields(item["type"])
    for k, v in list(item.items()):
        if k in cols:
            item[k] = _shift_colour(v, d["hue"], d["light"])
    for k in ("x", "y"):
        if k in item:
            item[k] = round(float(item[k]) + d["d" + k], 4)
    if "rotation" in item:
        item["rotation"] = round(float(item["rotation"]) + d["turn"], 4)
    if "scale" in item:
        item["scale"] = round(float(item["scale"]) * d["scale"], 4)
    if "opacity" in item:
        item["opacity"] = round(min(1.0, max(0.0, float(item["opacity"]) + d["opacity"])), 4)
    return item


def _vary_key(key: dict, d: dict) -> dict:
    if not isinstance(key.get("t"), str):               # a key timed on a marker follows the marker
        key["t"] = round(max(0.0, float(key["t"]) + d["time"]), 4)
    prop, v = key.get("prop"), key.get("v")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if prop in ("x", "y"):
            key["v"] = round(v + d["d" + prop], 4)
        elif prop == "rotation":
            key["v"] = round(v + d["turn"], 4)
        elif prop == "scale":
            key["v"] = round(v * d["scale"], 4)
        elif prop == "opacity":
            key["v"] = round(min(1.0, max(0.0, v + d["opacity"])), 4)
    elif isinstance(v, str):
        key["v"] = _shift_colour(v, d["hue"], d["light"])
    return key
