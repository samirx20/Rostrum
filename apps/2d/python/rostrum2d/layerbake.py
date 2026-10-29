"""Animation layers (rostrum_core.keys.layers) laid over the Base for the engine: a field with keys on a layer that is
on is written into the scene as `anim` keys, one per frame from 0 to the composition's length, ease `linear` (exact
at every frame), each the field's value with the whole stack laid over its Base (`layers.value`). The engine reads
plain keys and never sees a layer, so the canvas, the looks and the export draw it the same way (one path:
scene.prepare). The Base is the field's own keys or still value, or an expression's per-frame keys (exprbake) when it
has one; an auto layout's fields (layoutbake) are laid out over all of it. A path's shape and width profile (`d`
keys) and toggles are never layered. A document without layers, or whose layers hold no keys, bakes nothing: it
reads exactly as before.
"""
from __future__ import annotations

import math

from rostrum_core.keys import keys_of, layers as L, track_value

from . import fields as F
from .evaluate import placed
from .exprbake import items_of


def _layered(item: dict, live: set[str]) -> set[str]:
    """The number and colour fields of `item` the engine draws with keys on a layer that is on."""
    from .scene import python_only
    skip = python_only(item["type"])
    return {k["prop"] for k in item.get("keys", []) if k.get(L.FIELD) in live and k["prop"] not in skip
            and F.param(item["type"], k["prop"]) is not None and F.key_field(item["type"], k["prop"]) != "d"}


def bake(doc: dict, comp: dict, fps: float, baked: dict | None = None) -> dict[str, dict[str, list]]:
    """{item id: {field: linear keys at every frame}} for every field of the composition that a layer moves.
    `doc`: the document (its layer stack); `comp`: the composition in composition seconds (retime.timed);
    `baked`: the expressions' keys (exprbake), the Base of the fields they drive."""
    stack = L.stack_of(doc)
    live = {x["id"] for x in stack if x.get("on", True)}
    if not live:
        return {}
    baked = baked or {}
    duration = comp.get("duration", F.defaults("comp")["duration"])
    n = max(1, math.ceil(duration * fps - 1e-9))
    times = [round(min(i / fps, duration), 6) for i in range(n + 1)]
    out: dict = {}
    for id_, item in items_of(comp).items():
        if item.get("type") not in F.ANIMATED_OWNERS or not (props := _layered(item, live)):
            continue
        for prop in sorted(props):
            given = baked.get(id_, {}).get(prop)
            keys = given or placed(keys_of(item, prop))
            still = item.get(prop, F.param(item["type"], prop).default)
            field = F.key_field(item["type"], prop)
            out.setdefault(id_, {})[prop] = [
                {"t": t, field: L.value(item, prop, t, stack, track_value(keys, t) if keys else still,
                                        lambda ks, at: track_value(placed(ks), at)), "ease": "linear"} for t in times]
    return out
