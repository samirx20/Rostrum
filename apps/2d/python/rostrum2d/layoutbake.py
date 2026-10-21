"""Auto layout into the scene (layout.py is the solver): for a composition with any laid-out group, the x / y (and
w / h) the layout gives each layer, solved at every frame from 0 to the composition's length and written as `anim`
keys, ease `linear` (exact at every frame), as expressions are (exprbake.py). The engine sees plain keys and never
the layout fields; a field the layout sets overrides that field's own keys and any expression on it. A value that
never changes is one key. Layout reads the layers' values with their expressions applied (a card whose height is
an expression re-flows the others).
"""
from __future__ import annotations

import math

from rostrum_core.keys import track_value

from . import fields as F, textsize
from .evaluate import resolve
from .exprbake import items_of
from .layout import has_layout, solve


def uses_layout(comp: dict) -> bool:
    return any(has_layout(i) for i in items_of(comp).values())


def bake(comp: dict, fps: float, baked: dict | None = None) -> dict[str, dict[str, list]]:
    """{item id: {field: keys}} for every field an auto layout sets; `baked` = the expressions' keys (exprbake)."""
    if not uses_layout(comp):
        return {}
    baked = baked or {}

    def props(item, t):
        p = resolve(item, t)
        for prop, keys in baked.get(item["id"], {}).items():
            p[prop] = track_value(keys, t)
        return p

    duration = comp.get("duration", F.defaults("comp")["duration"])
    n = max(1, math.ceil(duration * fps - 1e-9))
    times = [round(min(i / fps, duration), 6) for i in range(n + 1)]
    texts = [i for i in items_of(comp).values() if i["type"] == "text"]
    textsize.prime([props(item, t) for t in times for item in texts])     # every frame's texts in one engine trip
    tracks: dict[str, dict[str, list]] = {}
    for t in times:
        for item_id, values in solve(comp, t, props).items():
            for prop, v in values.items():
                tracks.setdefault(item_id, {}).setdefault(prop, []).append({"t": t, "v": v, "ease": "linear"})
    for fields in tracks.values():
        for prop, keys in fields.items():
            if len(keys) == n + 1 and all(k["v"] == keys[0]["v"] for k in keys):
                fields[prop] = keys[:1]
    return tracks
