"""review's cover facts, read from the document's boxes (review_sample): a character more than half hidden behind layers
in front of it, and a character on a bare set (apart from it and the background, almost nothing). Each fault is {kind, start, end, id, text} with times; no taste: a title revealed from
behind a shape, or a character peeking over a wall, may be meant."""
from __future__ import annotations

from .geometry import covers, drawn_box
from .review_sample import Sampled, quad_points, runs

HIDDEN_FROM = 0.5         # a character with more than this share of its body behind layers in front is hidden ...
HIDDEN_S = 1.0            # ... for this long or longer
BARE_THINGS = 3           # a set with fewer things than this (layers or groups, apart from the character and background) ...
BARE_BELOW = 0.15         # ... or covering under this share of the frame is bare ...
BARE_S = 3.0              # ... for this long or longer while the character shows
THING = 0.002             # a layer under this share of the frame is a speck, not a thing on the set


def _in_front(s: Sampled, n: dict) -> bool:
    """A layer that can hide what is under it: showing, not a text, drawn normally (an added light or a multiplied shadow
    tints, it does not hide), not a full-frame wash."""
    return s.seen(n) and n["type"] != "text" and n["props"].get("blend", "normal") == "normal" and not s.backdrop(n)


def _related(a: dict, b: dict) -> bool:
    return a["id"] in b["within"] or b["id"] in a["within"]


def _over(o: dict, box) -> float:
    """The share of `box` that layer o paints over: where its box meets `box`, by how much of that it paints (a 3 x 3 look)."""
    x0, y0, x1, y1 = box
    a, b, c, d = drawn_box(o)
    l, t, r, btm = max(x0, a), max(y0, b), min(x1, c), min(y1, d)
    if r <= l or btm <= t:
        return 0.0
    painted = sum(covers(o, l + (r - l) * u, t + (btm - t) * v) for u in (0.1, 0.5, 0.9) for v in (0.1, 0.5, 0.9)) / 9
    return (r - l) * (btm - t) / max((x1 - x0) * (y1 - y0), 1.0) * painted


def _rig_index(nodes: list[dict], rid: str) -> int | None:
    return next((k for k, n in enumerate(nodes) if n["id"] == rid and n["in_time"] and n["opacity"] >= 0.1), None)


def staging(s: Sampled) -> list[dict]:
    """Each character more than HIDDEN_FROM behind layers in front of it, and each one on a bare set (BARE_THINGS, BARE_BELOW),
    its longest stretch."""
    if not any(s.parts):
        return []
    hidden: dict[str, dict[int, tuple]] = {}
    bare: dict[str, dict[int, tuple]] = {}
    for i, (t, nodes) in enumerate(s.frames):
        for rid, quads in s.parts[i].items():
            k = _rig_index(nodes, rid)
            if k is None:
                continue
            pts = [(x, y) for q in quads for x, y in quad_points(q) if 0 <= x <= s.W and 0 <= y <= s.H]
            if not pts:
                continue
            front = [o for o in nodes[k + 1:] if _in_front(s, o) and rid not in o["within"]]
            by = {}
            for x, y in pts:
                o = next((o for o in front if covers(o, x, y)), None)
                if o is not None:
                    by[o["id"]] = by.get(o["id"], 0) + 1
            share = sum(by.values()) / len(pts)
            if share > HIDDEN_FROM:
                hidden.setdefault(rid, {})[i] = (share, sorted(by, key=by.get, reverse=True))
            things = {}
            for n in nodes:
                if n["id"] != rid and rid not in n["within"] and n["type"] != "text" and s.seen(n) and not s.backdrop(n) \
                        and s.share(drawn_box(n)) >= THING:
                    things.setdefault(n["within"][0] if n["within"] else n["id"], []).append(drawn_box(n))
            cover = float(s.cells([b for bs in things.values() for b in bs]).mean())
            if len(things) < BARE_THINGS or cover < BARE_BELOW:
                bare.setdefault(rid, {})[i] = (cover, sorted(things))
    out = []
    for rid, at in hidden.items():
        found = runs([i in at for i in range(len(s.times))], s.times, s.step, HIDDEN_S)
        if found:
            t0, t1, a, b = max(found, key=lambda r: r[1] - r[0])
            share, ids = max((at[i] for i in range(a, b + 1)), key=lambda r: r[0])
            names = ", ".join(f'"{x}"' for x in ids[:3])
            out.append({"kind": "rig_hidden", "start": t0, "end": t1, "id": rid, "ids": ids, "hidden_pct": round(100 * share),
                        "text": f'{t0:g}–{t1:g} s: character "{rid}" is {100 * share:.0f} % hidden behind {names} in front of it'})
    for rid, at in bare.items():
        found = runs([i in at for i in range(len(s.times))], s.times, s.step, BARE_S)
        if found:
            t0, t1, a, b = max(found, key=lambda r: r[1] - r[0])
            cover, ids = max((at[i] for i in range(a, b + 1)), key=lambda r: len(r[1]))
            what = (f'only {len(ids)} thing{"s" if len(ids) != 1 else ""} ({", ".join(chr(34) + x + chr(34) for x in ids[:3])}) '
                    if ids else "nothing ") + f"covering {100 * cover:.0f} % of the frame"
            out.append({"kind": "bare_set", "start": t0, "end": t1, "id": rid, "ids": ids, "set_pct": round(100 * cover),
                        "text": f'{t0:g}–{t1:g} s: character "{rid}" stands on a bare set: apart from it and the background, {what}'})
    return out


CHECKS = (staging,)       # a text crossed by a layer in front: review_layout.overlaps (with _over, _in_front from here)


def facts(s: Sampled) -> list[dict]:
    return [f for check in CHECKS for f in check(s)]
