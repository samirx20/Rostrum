"""review's limb facts read from the document (nothing drawn): an arm held nearly straight for a long stretch, and limbs
thin next to their body (rig/thin.py, named once per character over the whole film). A straight
arm reads as a stick in a small still; a bent elbow reads as a gesture. Arms are the two-bone chains limb() makes
(`<id>_upper` › `<id>_lower`) that no IK chain drives (an IK knee bends to its target, so legs are left out). Facts, not
taste: a pointing arm may be meant straight, so only a stretch of STRAIGHT_S or more is named."""
from __future__ import annotations

from rostrum2d.evaluate import value_at
from rostrum2d.rig import thin

STRAIGHT_DEG = 25.0       # an elbow bent less than this is "nearly straight" (20° still reads straight in a still)
STRAIGHT_S = 4.0          # ... for this long or longer is named


def arms(comp: dict) -> list[tuple[str, str, dict]]:
    """(rig id, arm id, its lower bone) for every arm in the composition's rigs."""
    out, todo = [], list(comp.get("layers", []))
    while todo:
        layer = todo.pop()
        todo.extend(layer.get("layers", []))
        if layer.get("type") != "rig":
            continue
        bones = {b["id"]: b for b in layer.get("bones", [])}
        driven = {k.get("bone") for k in layer.get("iks", [])}
        for bid, b in bones.items():
            stem = bid[:-len("_lower")]
            if bid.endswith("_lower") and b.get("parent") == f"{stem}_upper" and bid not in driven:
                out.append((layer["id"], stem, b))
    return out


def straight_arms(comp: dict, times: list[float], step: float) -> list[dict]:
    """Stretches of STRAIGHT_S or more where an arm's elbow stays bent under STRAIGHT_DEG; arms of one character straight
    over the same stretch are one line."""
    spans: dict[tuple, list[str]] = {}
    for rid, arm, lower in arms(comp):
        flags = [abs(float(value_at(lower, "rotation", t) or 0.0)) < STRAIGHT_DEG for t in times]
        for t0, t1 in _runs(times, flags, step):
            spans.setdefault((rid, t0, t1), []).append(arm)
    out = []
    for (rid, t0, t1), names in sorted(spans.items(), key=lambda kv: kv[0][1]):
        who = " and ".join(f'"{n}"' for n in names)
        out.append({"kind": "arms_straight", "start": t0, "end": t1, "id": rid, "ids": names,
                    "text": f'{t0:g}–{t1:g} s: character "{rid}" holds {"its arms" if len(names) > 1 else "an arm"} ({who}) '
                            f'nearly straight for {t1 - t0:g} s (elbow bent under {STRAIGHT_DEG:g}°: reads as a stick; '
                            f'bend the elbow with arm.pose({{t: {{"upper": a, "lower": b}}}}) or a bigger relax=)'})
    return out


def thin_limbs(comp: dict) -> list[dict]:
    """One line per character whose arms or legs are thin next to its body."""
    out = []
    for rig in thin.rigs(comp):
        rows = thin.thin_limbs(rig)
        if rows:
            out.append({"kind": "limbs_thin", "start": 0.0, "end": float(comp.get("duration", 5.0)), "id": rig["id"],
                        "ids": [i for r in rows for i in r["ids"]], "text": thin.say(rig["id"], rows)})
    return out


def _runs(times: list[float], flags: list[bool], step: float) -> list[tuple[float, float]]:
    out, a = [], None
    for i, on in enumerate(flags + [False]):
        if on and a is None:
            a = i
        elif not on and a is not None:
            t0, t1 = times[a], times[i - 1] + step
            if t1 - t0 >= STRAIGHT_S - 1e-9:
                out.append((round(t0, 2), round(t1, 2)))
            a = None
    return out
