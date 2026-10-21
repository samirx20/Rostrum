"""Facts about a composition's motion that an agent should know before it looks: overlapping entrances, stretches
where nothing moves, layers not showing at the end, keys that do nothing. Each finding is a plain sentence plus
the numbers; there is no score and no opinion about taste.
"""
from __future__ import annotations

from rostrum2d.evaluate import key_value, keys_of

from .geometry import comp_size, flatten, problems_showing
from .motion_facts import HOLD_MIN_S, all_layers, r, windows


def finding(kind: str, text: str, **data) -> dict:
    return {"kind": kind, "text": text, **data}


def entrance_overlaps(facts: list[dict]) -> list[dict]:
    """Layers whose first moving stretch overlaps another layer's; the overlap in seconds."""
    ent = sorted(((f["entrance"], f["id"]) for f in facts if f["entrance"]), key=lambda e: e[0])
    out = []
    for i, ((a0, a1), a) in enumerate(ent):
        for (b0, b1), b in ent[i + 1:]:
            if b0 >= a1:
                break
            both = round(min(a1, b1) - b0, 3)
            how = "start together" if abs(a0 - b0) < 1e-6 else f"start {r(b0 - a0, 2)} s apart"
            out.append(finding("entrances_overlap", f"{a} ({a0}–{a1} s) and {b} ({b0}–{b1} s) move at the same time for {both} s; they {how}.",
                               layers=[a, b], overlap_s=both, apart_s=r(b0 - a0)))
    return out


def quiet_spans(facts: list[dict], duration: float) -> list[dict]:
    """Stretches of the whole composition where nothing at all moves (the end counts)."""
    wins = windows([{"start": a, "end": b} for f in facts for a, b in f["moving"]])
    edges = [0.0, *[x for w in wins for x in w], duration]
    return [finding("nothing_moves", f"Nothing moves from {r(a, 2)} to {r(b, 2)} s ({r(b - a, 2)} s).", start=r(a), end=r(b))
            for a, b in zip(edges[::2], edges[1::2]) if b - a >= HOLD_MIN_S]


def not_showing(comp: dict, t: float) -> list[dict]:
    w, h = comp_size(comp)
    out = []
    for node in flatten(comp, t):
        if node["type"] == "group":
            continue
        why = problems_showing(node, w, h)
        if why:
            out.append(finding("not_showing", f'{node["id"]} is not on screen at {r(t, 2)} s: {", ".join(why)}.', layer=node["id"], at=r(t), reasons=why))
    return out


def never_shown(comp: dict, fps: float, duration: float) -> list[dict]:
    """Layers that are not visible at any frame of the composition."""
    w, h = comp_size(comp)
    n = max(1, min(900, round(duration * fps)))
    seen: set[str] = set()
    ids = {node["id"] for node in flatten(comp, 0.0) if node["type"] != "group"}
    for i in range(n):
        for node in flatten(comp, min(duration * i / n, duration - 1e-6)):
            if node["type"] != "group" and not problems_showing(node, w, h):
                seen.add(node["id"])
    return [finding("never_shown", f"{i} is never on screen between 0 and {r(duration, 2)} s.", layer=i) for i in sorted(ids - seen)]


def dead_keys(comp: dict, duration: float) -> list[dict]:
    out = []
    for layer, _ in all_layers(comp):
        for owner in (layer, *layer.get("effects", []), *layer.get("masks", [])):
            label = layer["id"] if owner is layer else f'{layer["id"]}.{owner["id"]}'
            for prop in sorted({k["prop"] for k in owner.get("keys", [])}):
                keys = keys_of(owner, prop)
                vals = [key_value(k) for k in keys]
                if len(keys) == 1:
                    out.append(finding("key_does_nothing", f"{label}.{prop} has one key (at {keys[0]['t']} s): a single key never moves; the value is held at {vals[0]} the whole time.", owner=label, field=prop))
                elif len(set(vals)) == 1:
                    out.append(finding("key_does_nothing", f"{label}.{prop} has {len(keys)} keys that all say {vals[0]}: it never changes.", owner=label, field=prop))
                for k in keys:
                    if k["t"] >= duration:
                        out.append(finding("key_after_end", f"{label}.{prop} has a key at {k['t']} s, at or after the composition ends ({r(duration, 2)} s); it is never reached.", owner=label, field=prop, at=k["t"]))
                    elif owner is layer and k["t"] >= layer.get("end", 36000.0):
                        out.append(finding("key_after_end", f"{label}.{prop} has a key at {k['t']} s, after the layer's own end ({layer['end']} s).", owner=label, field=prop, at=k["t"]))
    return out
