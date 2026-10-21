"""When a composition's layers can be seen: the one rule for which moments are looked at. The Problems "never seen"
check (diagnose.py) and the moment a screen opens on (`first_seen`) both use it.

The moments: even samples over the composition, its last frame included, and each layer's own moments (start, end,
each key, and those of the groups around it, plus the moment after each), so a short pop or an end fade between two
even samples is not missed. Times are composition seconds: pass the composition after retime.timed.
"""
from __future__ import annotations

import math

from rostrum_core.keys import animated, keys_of

from . import fields as F
from .mcp.geometry import comp_size, flatten, problems_showing

SAMPLES = 24          # even moments looked at across the composition's length
MATTE_ONLY = ("drawn only as the track matte", "its track matte")    # shown through another layer: not "unseen"


def _span(comp: dict) -> tuple[float, float]:
    duration = comp.get("duration", F.defaults("comp")["duration"])
    return duration, max(0.0, duration - 1.0 / comp.get("fps", 30))


def _even(comp: dict) -> list[float]:
    duration, last = _span(comp)
    return [duration * i / SAMPLES for i in range(SAMPLES)] + [last]


def own_moments(comp: dict, ids: set | None = None) -> dict[str, set]:
    """For each layer id (None = every layer): its own moments, kept inside the composition."""
    duration, last = _span(comp)
    out: dict[str, set] = {}

    def walk(layers, above):
        for item in layers:
            marks = above | {item.get("start", 0.0), item.get("end", math.inf)} | {k["t"] for p in animated(item) for k in keys_of(item, p)}
            if ids is None or item["id"] in ids:
                out[item["id"]] = {round(min(max(t + d, 0.0), last), 4) for t in marks if math.isfinite(t) and t < duration for d in (0.0, 1e-3)}
            walk(item.get("layers", []), marks)

    walk(comp.get("layers", []), set())
    return out


def unseen(comp: dict) -> dict[str, dict[str, int]]:
    """Layers seen at none of the moments: {id: {reason: how many moments it was the reason}}. A layer shown only as
    another's track matte is left out (that is what it is for)."""
    w, h = comp_size(comp)
    seen, why = set(), {}

    def look(t, only=None):
        for node in flatten(comp, t):
            if only is not None and node["id"] not in only:
                continue
            reasons = problems_showing(node, w, h)
            if not reasons:
                seen.add(node["id"])
            for r in reasons:
                why.setdefault(node["id"], {}).setdefault(r, 0)
                why[node["id"]][r] += 1

    for t in _even(comp):
        look(t)
    own = own_moments(comp, set(why) - seen)            # look again only for the layers not seen yet
    for t in sorted({t for ts in own.values() for t in ts}):
        look(t, {i for i, ts in own.items() if t in ts})
    return {i: r for i, r in why.items() if i not in seen and not any(x.startswith(MATTE_ONLY) for x in r)}


def first_seen(comp: dict) -> float | None:
    """The first of the moments at which something comes into view: where a screen opens. A still layer (no keys, no
    start or end inside the composition, nor in the groups around it: a background, a vignette) doesn't count unless
    nothing else ever shows. None = nothing is ever seen."""
    w, h = comp_size(comp)
    own = own_moments(comp)
    still = {i for i, ts in own.items() if ts <= {0.0, 0.001}}
    times = sorted(set(_even(comp)).union(*own.values()))

    def showing(t, ignore):
        return any(not problems_showing(n, w, h) for n in flatten(comp, t) if n["id"] not in ignore)

    return next((t for t in times if showing(t, still)), next((t for t in times if showing(t, set())), None))
