"""Auto layout into the scene (layout.py is the solver): for a composition with any laid-out group, the x / y (and
w / h, a text's boxWidth) the layout gives each layer, solved at every frame from 0 to the composition's length and
written as `anim` keys, ease `linear` (exact at every frame), as expressions are (exprbake.py). The frames' layout trees
go to the engine together (FRAMES a request); a frame whose trees are the same as one before is not asked again. The engine sees plain keys and never
the layout fields; a field the layout sets overrides that field's own keys and any expression on it. A value that
never changes is one key. Layout reads the layers' values with their expressions applied (a card whose height is
an expression re-flows the others).

Each top-level layer's layout is solved on its own and kept (_KEPT) while it is the very same object (documents are
copy on write: an edit makes new objects only for what it touched), in the same composition settings, with the same
expression keys inside it: a script re-run that changed one section solves only that section again (a 70 s film:
~4 s for every frame of every section, before).
"""
from __future__ import annotations

import math

from rostrum_core.keys import track_value

from . import fields as F
from .evaluate import resolve
from .exprbake import items_of
from .layout import Plan, has_layout, laid_out, lay_out, prime_texts

FRAMES = 60                 # frames' layout trees a request: one round trip a couple of seconds of film
KEEP = 512                  # top-level layers' solved layouts kept (oldest dropped)
_KEPT: dict[str, tuple] = {}   # top-level layer id -> (the layer object, comp settings, its expression keys, its tracks)


def uses_layout(comp: dict) -> bool:
    return any(has_layout(i) for i in items_of(comp).values())


def bake(comp: dict, fps: float, baked: dict | None = None) -> dict[str, dict[str, list]]:
    """{item id: {field: keys}} for every field an auto layout sets; `baked` = the expressions' keys (exprbake)."""
    if not uses_layout(comp):
        return {}
    baked = baked or {}
    settings = (fps, {k: v for k, v in comp.items() if k != "layers"})
    out: dict[str, dict[str, list]] = {}
    for layer in comp.get("layers", []):
        if not laid_out(layer):
            continue
        mine = {i: baked[i] for i in items_of(layer) if i in baked}
        kept = _KEPT.get(layer["id"])
        if not (kept and kept[0] is layer and kept[1] == settings and kept[2] == mine):
            kept = (layer, settings, mine, _solve({**comp, "layers": [layer]}, fps, baked))
            _KEPT.pop(layer["id"], None)
            _KEPT[layer["id"]] = kept
            while len(_KEPT) > KEEP:
                _KEPT.pop(next(iter(_KEPT)))
        out.update({i: dict(fields) for i, fields in kept[3].items()})
    return out


def _solve(comp: dict, fps: float, baked: dict) -> dict[str, dict[str, list]]:
    """bake's work for the layers of `comp`, every frame."""

    def props(item, t):
        p = resolve(item, t)
        for prop, keys in baked.get(item["id"], {}).items():
            p[prop] = track_value(keys, t)
        return p

    duration = comp.get("duration", F.defaults("comp")["duration"])
    n = max(1, math.ceil(duration * fps - 1e-9))
    times = [round(min(i / fps, duration), 6) for i in range(n + 1)]
    tracks: dict[str, dict[str, list]] = {}
    for at in range(0, len(times), FRAMES):
        plans = [Plan(comp, t, props) for t in times[at:at + FRAMES]]
        answers = lay_out([tree for plan in plans for tree in plan.trees])
        pairs, i = [], 0
        for plan in plans:
            pairs.append((plan, answers[i:i + len(plan.trees)]))
            i += len(plan.trees)
        prime_texts(pairs)                                              # the frames' texts in two engine trips
        for plan, got in pairs:
            for item_id, values in plan.result(got, primed=True).items():
                for prop, v in values.items():
                    tracks.setdefault(item_id, {}).setdefault(prop, []).append({"t": plan.t, "v": v, "ease": "linear"})
    items = items_of(comp)
    for item_id, fields in tracks.items():
        for prop, keys in fields.items():
            if len(keys) < n + 1:                # set at some frames only (a text narrowed for a while): its own
                have = {k["t"] for k in keys}    # value at the others, so no key reaches across them
                keys += [{"t": t, "v": props(items[item_id], t)[prop], "ease": "linear"} for t in times if t not in have]
                keys.sort(key=lambda k: k["t"])
            if len(keys) == n + 1 and all(k["v"] == keys[0]["v"] for k in keys):
                fields[prop] = keys[:1]
    return tracks
