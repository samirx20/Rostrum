"""Motion facts read from a composition's keys: no rendering. Per layer: its moves (one per stretch between two keys
that changes a value), the merged moving windows, holds between them, the position path and peak speeds.
Facts only; no taste.
"""
from __future__ import annotations

import math

from rostrum2d.evaluate import key_value, keys_of, value_at

HOLD_MIN_S = 0.5          # a still stretch shorter than this isn't reported as a hold


def r(x: float, n: int = 3) -> float:
    return round(float(x), n)


def owners(layer: dict):
    """(prefix, owner) for the layer itself and for each of its effects and masks (their fields show as 'glow.radius')."""
    yield "", layer
    for child in (*layer.get("effects", []), *layer.get("masks", [])):
        yield child["id"] + ".", child


def moves_of(owner: dict, prefix: str, fps: float) -> list[dict]:
    """One move per stretch between two consecutive keys of a field where the value changes."""
    out = []
    for prop in sorted({k["prop"] for k in owner.get("keys", [])}):
        keys = keys_of(owner, prop)
        for k0, k1 in zip(keys, keys[1:]):
            a, b = key_value(k0), key_value(k1)
            if a == b:
                continue
            move = {"field": prefix + prop, "start": r(k0["t"]), "end": r(k1["t"]), "from": a, "to": b, "ease": k0.get("ease", "smooth")}
            if move["ease"] == "hold":
                move["jumps_at"] = move["end"]
            elif isinstance(a, (int, float)):
                move.update(_speed(owner, prop, k0["t"], k1["t"], a, b, fps))
            out.append(move)
    return sorted(out, key=lambda m: (m["start"], m["field"]))


def _speed(owner, prop, t0, t1, a, b, fps) -> dict:
    n = max(4, min(240, round((t1 - t0) * fps)))
    ts = [t0 + (t1 - t0) * i / n for i in range(n + 1)]
    vs = [value_at(owner, prop, t) for t in ts]
    rates = [abs(v1 - v0) / (ts[i + 1] - ts[i]) for i, (v0, v1) in enumerate(zip(vs, vs[1:]))]
    peak = max(range(len(rates)), key=rates.__getitem__)
    travel = b - a
    past = max((v - b) * (1 if travel > 0 else -1) for v in vs)
    facts = {"peak_rate": r(rates[peak], 2), "peak_at": r(ts[peak] + (ts[1] - ts[0]) / 2)}
    if past > 0.01 * abs(travel):
        facts["overshoot"] = r(past, 3)             # how far it goes beyond the landing value before settling
    return facts


def windows(moves: list[dict]) -> list[tuple[float, float]]:
    """The moves merged into the stretches of time where something of this layer is moving."""
    out: list[list[float]] = []
    for m in sorted(moves, key=lambda m: m["start"]):
        if out and m["start"] <= out[-1][1]:
            out[-1][1] = max(out[-1][1], m["end"])
        else:
            out.append([m["start"], m["end"]])
    return [(a, b) for a, b in out]


def holds_between(wins: list[tuple[float, float]]) -> list[dict]:
    return [{"from": r(a1), "to": r(b0), "seconds": r(b0 - a1, 2)} for (_, a1), (b0, _) in zip(wins, wins[1:]) if b0 - a1 >= HOLD_MIN_S]


def path_of(layer: dict, moves: list[dict], fps: float) -> dict | None:
    """Where the layer's anchor travels: start, end, length and peak speed (px/s, in its parent's coordinates)."""
    xy = [m for m in moves if m["field"] in ("x", "y")]
    if not xy:
        return None
    t0, t1 = min(m["start"] for m in xy), max(m["end"] for m in xy)
    n = max(4, min(400, round((t1 - t0) * fps)))
    ts = [t0 + (t1 - t0) * i / n for i in range(n + 1)]
    pts = [(value_at(layer, "x", t), value_at(layer, "y", t)) for t in ts]
    steps = [math.dist(p, q) / (ts[i + 1] - ts[i]) for i, (p, q) in enumerate(zip(pts, pts[1:]))]
    peak = max(range(len(steps)), key=steps.__getitem__)
    return {"from": [r(pts[0][0], 1), r(pts[0][1], 1)], "to": [r(pts[-1][0], 1), r(pts[-1][1], 1)],
            "start": r(t0), "end": r(t1), "length_px": r(sum(math.dist(p, q) for p, q in zip(pts, pts[1:])), 1),
            "peak_speed_px_s": r(steps[peak], 1), "peak_at": r(ts[peak] + (ts[1] - ts[0]) / 2)}


def layer_facts(layer: dict, fps: float, within: tuple = ()) -> dict:
    moves = [m for prefix, o in owners(layer) for m in moves_of(o, prefix, fps)]
    wins = windows(moves)
    fields = sorted({k["prop"] for k in layer.get("keys", [])} | {c["id"] + "." + k["prop"] for c in (*layer.get("effects", []), *layer.get("masks", [])) for k in c.get("keys", [])})
    return {"id": layer["id"], "type": layer["type"], "within": list(within), "animated_fields": fields, "moves": moves,
            "moving": [[r(a), r(b)] for a, b in wins], "entrance": [r(wins[0][0]), r(wins[0][1])] if wins else None,
            "holds": holds_between(wins), "path": path_of(layer, moves, fps)}


def all_layers(comp: dict, within: tuple = ()):
    for layer in comp.get("layers", []):
        yield layer, within
        if layer["type"] == "group":
            yield from all_layers(layer, within + (layer["id"],))
