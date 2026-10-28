"""review's whole-frame facts, read from the document's boxes (review_sample): a frame almost empty in the middle of the film,
opening shots that look alike (the same layers on the same ground, about as big), and an end picture that holds unchanged
for more than a fifth of the film. Each fault is {kind, start, end, id, text} with times; no taste: a quiet beat, a
repeated motif or a long end card may be meant."""
from __future__ import annotations

from rostrum2d.evaluate import value_at

from .geometry import aabb, drawn_box
from .review_sample import Sampled, runs

SPARSE_BELOW = 0.05       # anything but the background covering under this share of the frame is near-empty ...
SPARSE_SPAN = (0.15, 0.85)  # ... between these shares of the film (an opening or closing card may start or end bare)
SPARSE_S = 2.0            # ... for this long or longer
OPEN_S = 10.0             # the opening: shots starting in the first this many seconds ...
OPEN_SHOTS = 3            # ... the first this many of them
SHOT_S = 1.0              # a shot lasts at least this long (a fast move is not a string of cuts)
CUT_SAME, CUT_OVERLAP = 0.5, 0.3   # a cut: under this share of the layers stay, or covered areas overlap under this share
ALIKE_SAME, ALIKE_SIZE = 0.8, 0.67  # alike: this share of the layers the same, covered areas within this ratio, same ground
END_SHARE = 0.2           # an unchanged last picture held longer than this share of the film is named
END_MOVE, END_FADE, END_TURN = 0.03, 0.1, 10.0   # unchanged: boxes within this share of the width, opacity, bone degrees


def _subjects(s: Sampled, i: int) -> list[tuple[str, tuple]]:
    """(top-level id, box) of what shows at sample i apart from the background; a character by its posed parts."""
    nodes = s.frames[i][1]
    out = [(n["within"][0] if n["within"] else n["id"], drawn_box(n)) for n in nodes if s.seen(n) and not s.backdrop(n)]
    parts = s.parts[i] if any(n["type"] == "rig" and n["in_time"] for n in nodes) else {}
    return out + [(rid, aabb(q)) for rid, quads in parts.items() for q in quads]


def _names(ids) -> str:
    ids = list(dict.fromkeys(ids))
    return ", ".join(f'"{i}"' for i in ids[:3]) + (" …" if len(ids) > 3 else "")


def sparse(s: Sampled) -> list[dict]:
    """Stretches inside SPARSE_SPAN where what shows covers under SPARSE_BELOW of the frame."""
    lo, hi = SPARSE_SPAN[0] * s.duration, SPARSE_SPAN[1] * s.duration
    rows, flags = [], []
    for i, t in enumerate(s.times):
        inside = lo - 1e-9 <= t < hi
        subs = _subjects(s, i) if inside else []
        cover = float(s.cells([b for _, b in subs]).mean()) if inside else 1.0
        rows.append((cover, [k for k, _ in subs]))
        flags.append(cover < SPARSE_BELOW)
    out = []
    for t0, t1, a, b in runs(flags, s.times, s.step, SPARSE_S):
        most = max(rows[a:b + 1], key=lambda r: r[0])
        ids = [k for r in rows[a:b + 1] for k in r[1]]
        what = f"only {_names(ids)} showing" if ids else "nothing but the background"
        out.append({"kind": "sparse", "start": t0, "end": t1, "id": ids[0] if ids else "", "cover_pct": round(100 * most[0], 1),
                    "text": f'{t0:g}–{t1:g} s: the frame is nearly empty mid-film: anything but the background covers at most '
                            f'{_pct(most[0])} of it ({what})'})
    return out


def _pct(share: float) -> str:
    return "under 1 %" if share < 0.01 else f"{100 * share:.0f} %"


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def opening(s: Sampled) -> list[dict]:
    """The first OPEN_SHOTS shots of the opening, cut where the layers, the ground or the covered area jump; the ones that
    look alike (the same layers on the same ground, a similar covered area) are one line."""
    if len(s.times) < 2:
        return []
    look = []
    for i in range(len(s.times)):
        subs = _subjects(s, i)
        look.append((frozenset(k for k, _ in subs), s.background(s.frames[i][1]), s.cells([b for _, b in subs])))
    starts = [0]
    for j in range(1, len(look)):
        (ia, ga, ca), (ib, gb, cb) = look[j - 1], look[j]
        union = (ca | cb).sum()
        if _jaccard(ia, ib) < CUT_SAME or ga != gb or union and (ca & cb).sum() / union < CUT_OVERLAP:
            starts.append(j)
    shots = [(a, b) for a, b in zip(starts, starts[1:] + [len(look)]) if (b - a) * s.step >= SHOT_S - 1e-9 and s.times[a] < OPEN_S]
    shots = shots[:OPEN_SHOTS]
    mid = [look[(a + b - 1) // 2] for a, b in shots]
    alike = set()
    for x in range(len(shots)):
        for y in range(x + 1, len(shots)):
            (ia, ga, ca), (ib, gb, cb) = mid[x], mid[y]
            sa, sb = ca.mean(), cb.mean()
            if ia and ga == gb and _jaccard(ia, ib) >= ALIKE_SAME and min(sa, sb) >= ALIKE_SIZE * max(sa, sb):
                alike |= {x, y}
    if not alike:
        return []
    picked = sorted(alike)
    spans = [(s.times[shots[k][0]], round(s.times[shots[k][1] - 1] + s.step, 2)) for k in picked]
    ids = sorted(set().union(*(mid[k][0] for k in picked)))
    pcts = [round(100 * mid[k][2].mean()) for k in picked]
    return [{"kind": "alike_open", "start": spans[0][0], "end": spans[-1][1], "id": ids[0], "ids": ids, "spans": spans,
             "text": f'{", ".join(f"{a:g}–{b:g} s" for a, b in spans)}: {len(picked)} opening shots look alike: the same '
                     f'layers ({_names(ids)}) on the same {mid[picked[0]][1]} ground, covering {_pct_range(pcts)} % of the frame'}]


def _pct_range(pcts: list[int]) -> str:
    return f"{min(pcts)}" if min(pcts) == max(pcts) else f"{min(pcts)}–{max(pcts)}"


def _bones(comp: dict) -> list[dict]:
    out, todo = [], list(comp.get("layers", []))
    while todo:
        layer = todo.pop()
        todo.extend(layer.get("layers", []))
        out.extend(layer.get("bones", []) if layer.get("type") == "rig" else [])
    return out


def end_hold(s: Sampled) -> list[dict]:
    """From when the last picture stays the same (the same layers, boxes within END_MOVE, opacity within END_FADE, bones within
    END_TURN degrees) up to the end, when that is longer than END_SHARE of the film and not the whole film."""
    if len(s.times) < 2:
        return []
    bones = _bones(s.comp)

    def state(i: int):
        t, nodes = s.frames[i]
        return ({n["id"]: (drawn_box(n), n["opacity"]) for n in nodes if s.seen(n)},
                [float(value_at(b, "rotation", t) or 0.0) for b in bones])

    last, last_bones = state(len(s.times) - 1)
    move = END_MOVE * s.W
    first = len(s.times) - 1
    for i in range(len(s.times) - 2, -1, -1):
        now, now_bones = state(i)
        same = (now.keys() == last.keys() and all(abs(a - b) <= move for k in now for a, b in zip(now[k][0], last[k][0]))
                and all(abs(now[k][1] - last[k][1]) <= END_FADE for k in now)
                and all(abs(a - b) <= END_TURN for a, b in zip(now_bones, last_bones)))
        if not same:
            break
        first = i
    t0 = s.times[first]
    held = s.duration - t0
    if first == 0 or held <= END_SHARE * s.duration + 1e-9 or not last:
        return []
    return [{"kind": "end_held", "start": t0, "end": s.duration, "id": next(iter(last)),
             "text": f'{t0:g} s to the end: the last picture holds unchanged for {held:g} s, {100 * held / s.duration:.0f} % of '
                     f'the film ({_names(last)} in place, nothing moves or changes)'}]


CHECKS = (sparse, opening, end_hold)


def facts(s: Sampled) -> list[dict]:
    return [f for check in CHECKS for f in check(s)]
