"""`note.fit_key`: the selected notes that are outside the key move to the nearest note of the key (the key playing at
each note's own time, or `key` when given). Notes already in the key are never touched, a chord (a list of pitches)
is fitted tone by tone, and a note keeps the spelling it had. One rule for the screen's Fit to key (Ctrl+K) and agents.
"""
from __future__ import annotations

from rostrum_core import Param, codes

from . import keys
from .ops_transpose import NO_KEY, _shifted
from .registry import REGISTRY
from .select_time import start_of

KEY = Param.text("key", group="Fit", label="Key", help='A key to fit to, e.g. "D minor". Leave out to use the song\'s key at each note.')
DIRECTION = Param.choice("direction", ["nearest", "down", "up"], group="Fit", label="Which way",
                         help="nearest: the closest note of the key (a tie goes down); down or up: always that way.")


def _fit(k: int, key: str, way: str) -> int:
    if keys.in_key(k, key):
        return k
    if way == "nearest":
        return keys.snap(k, key)
    return keys.step_in_key(k, key, 1 if way == "up" else -1)


@REGISTRY.operation("note.fit_key", "Move the selected notes that are outside the key to the nearest note of the key "
                    "(`direction` \"down\" or \"up\" to always go one way). The key is the song's key at each note's time, "
                    "or `key` (\"D minor\"). Notes already in the key are not touched; a chord is fitted tone by tone. "
                    "Fails if there is no key (set one with key.add).", target="note", params=[KEY, DIRECTION], label="Fit to key")
def fit_key(ctx, targets, args):
    given, way = args.get("key"), args.get("direction", "nearest")
    if given is not None and keys.parse(given) is None:
        ctx.fail(codes.BAD_ARGUMENT, "key", f"{given!r} is not a key", keys.FORMS)
    plan, moved = [], 0
    for t in targets:
        n = ctx.item(t)
        key = given or keys.key_for(ctx.doc, start_of(ctx.doc, n))
        if not key:
            ctx.fail(codes.BAD_ARGUMENT, "key", NO_KEY, hint='Set a key (key.add {at: 0, key: "D minor"}) or give `key`.',
                     plain=NO_KEY + ".")
        pitch = n["pitch"]
        tones = pitch if isinstance(pitch, list) else [pitch]
        new = [_shifted(p, _fit(keys.midi(p), key, way) - keys.midi(p), key) for p in tones]
        if new != tones:
            plan.append((t, new if isinstance(pitch, list) else new[0]))
    for t, new in plan:
        ctx.set(t, "pitch", new)
