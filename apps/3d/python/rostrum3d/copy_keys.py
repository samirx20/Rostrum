"""Keyed copies (brief 26a follow-up, contract v1.25): one copy of a copies item moving by keys on its own x y z rx ry rz,
in the copies item's own space like a held copy. Turn into keys on a falling copies item writes them (sim.to_keys: each copy
follows its fall); copies.key sets one by hand (a nudge); copies.release lets a copy go back to the layout.

Stored on the copies item as `copyKeys` rows [copy, prop, t, v, ease, sim]: prop 0..5 = x y z rx ry rz, t in seconds,
ease 0 linear / 1 hold / 2 smooth, sim 1 when the simulation named by `copyKeysFrom` wrote it (a nudge keeps the 1, as a
nudged key keeps its `from`; a key a person adds is 0). The compiler bakes them to one value per frame of the shot: the
held copy's `anim` (ENGINE_CONTRACT § Copies).
"""
from __future__ import annotations

from rostrum_core.keys.easing import ease

from .copies_fields import COPY_KEYS as KEYS, COPY_KEYS_FROM as FROM

PROPS = ("x", "y", "z", "rx", "ry", "rz")
EASES = ("linear", "hold", "smooth")


def keys_map(item: dict) -> dict[int, dict[str, list[dict]]]:
    """{copy: {prop: [{"t", "v", "ease", "sim"}] by time}}."""
    out: dict[int, dict[str, list[dict]]] = {}
    for c, p, t, v, e, sim in item.get(KEYS) or []:
        out.setdefault(int(c), {}).setdefault(PROPS[int(p)], []).append(
            {"t": t, "v": v, "ease": EASES[int(e)], "sim": bool(sim)})
    for props in out.values():
        for ks in props.values():
            ks.sort(key=lambda k: k["t"])
    return out


def rows(keyed: dict[int, dict[str, list[dict]]]) -> list[list[float]] | None:
    """The rows to store (None when no copy is keyed: an empty list is not a valid set of points)."""
    out = [[c, PROPS.index(p), round(k["t"], 4), round(k["v"], 6), EASES.index(k["ease"]), int(k["sim"])]
           for c in sorted(keyed) for p in PROPS for k in sorted(keyed[c].get(p, []), key=lambda k: k["t"])]
    return out or None


def _track(keys: list[dict], times: list[float]) -> list[float]:
    """The keys' value at each of `times` (ascending): held before the first and after the last, eased between."""
    out, i = [], 0
    for t in times:
        while i + 1 < len(keys) and keys[i + 1]["t"] <= t:
            i += 1
        k0 = keys[i]
        if t <= k0["t"] or i + 1 == len(keys):
            out.append(k0["v"])
            continue
        k1 = keys[i + 1]
        out.append(k0["v"] + (k1["v"] - k0["v"]) * ease(k0, (t - k0["t"]) / (k1["t"] - k0["t"])))
    return out


def baked(item: dict, times: list[float]) -> dict[int, dict[str, list[float]]]:
    """{copy: {prop: one value per time}} for every keyed copy (times: the shot's frames in seconds)."""
    return {c: {p: [round(v, 6) for v in _track(ks, times)] for p, ks in props.items() if ks}
            for c, props in keys_map(item).items()}


def held_nodes(item: dict, held: dict[int, dict], times: list[float]) -> list[dict]:
    """The node's `held` list: each held copy as it is, and each keyed one with its `anim` (a keyed copy that is not
    held gives only what is keyed: the layout keeps the rest, its size too)."""
    keyed = baked(item, times)
    out = []
    for c in sorted({*held, *keyed}):
        row = {"copy": c, **held.get(c, {})}
        if c in keyed:
            row.update({p: vals[0] for p, vals in keyed[c].items()})
            row["anim"] = keyed[c]
        out.append(row)
    return out
