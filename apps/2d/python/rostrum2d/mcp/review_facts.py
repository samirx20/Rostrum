"""review's facts read from the document (cheap, nothing drawn): framing held, a pose held, a title touching the frame edge,
an old heading still faintly showing behind a new one, a set of parts (a chart's bars) not yet showing while the rest of
its group does, and the beats the agent declared. Each fault is {kind, start, end, text, …} with times; no taste."""
from __future__ import annotations

from rostrum_core.motion.report import stem

from rostrum2d.frame import view

from .geometry import comp_size, drawn_box, flatten
from . import edge_cut

HOLD_FRAMING_S = 10.0     # the frame (camera) unchanged this long is named
FRAMING_SAME = 0.004      # ... moves under this share of the picture (and zoom / turn this small) count as unchanged
HOLD_POSE_S = 6.0         # a character's pose unchanged this long is named
POSE_SAME = 0.035         # ... its parts move under this share of its height (relative to its own body)
EDGE_CUT = 0.03           # a text with this share of its own width / height past an edge is cut off
SHOWN = 0.25              # opacity from which a text counts as read
FAINT = (0.03, 0.35)      # a text this see-through, over another fully shown one: a ghost
GHOST_S, HOLLOW_S = 1.0, 2.0
SET_MIN = 3               # this many siblings named alike (bar_0, bar_1 …) make a set


def _runs(times: list[float], flags: list, step: float, least: float):
    """(start, end, first index, last index) of each run of truthy flags lasting at least `least` seconds."""
    out, a = [], None
    for i, on in enumerate(list(flags) + [False]):
        if on and a is None:
            a = i
        elif not on and a is not None:
            t0, t1 = times[a], min(times[i - 1] + step, times[-1] + step)
            if t1 - t0 >= least - 1e-9:
                out.append((round(t0, 2), round(t1, 2), a, i - 1))
            a = None
    return out


def _span(a: float, b: float) -> str:
    return f"{a:g}–{b:g} s"


def shots(comp: dict, times: list[float]) -> list[tuple | None]:
    return [None if (s := view.shot(comp, t)) is None else (s.x, s.y, s.zoom, s.roll) for t in times]


def _same_shot(a, b, w: float) -> bool:
    if a is None or b is None:
        return a is b
    return (abs(a[0] - b[0]) < FRAMING_SAME * w and abs(a[1] - b[1]) < FRAMING_SAME * w
            and abs(a[2] / (b[2] or 1) - 1) < FRAMING_SAME * 2 and abs(a[3] - b[3]) < 0.5)


def framing(comp: dict, times: list[float], step: float) -> list[dict]:
    """Stretches of HOLD_FRAMING_S or more where the frame neither moves nor cuts (measured from each stretch's first shot)."""
    w, _ = comp_size(comp)
    got, held, anchor = shots(comp, times), [], None
    for s in got:
        held.append(anchor is not None and _same_shot(anchor, s, w))
        if not held[-1]:
            anchor = s
    held = [h or (i + 1 < len(held) and held[i + 1]) for i, h in enumerate(held)]     # the stretch's first sample is in it too
    whole = got[0] is None and all(s is None for s in got)
    out = []
    for t0, t1, _, _ in _runs(times, held, step, HOLD_FRAMING_S):
        everything = t0 <= times[0] + 1e-9 and t1 >= times[-1] + step - 1e-9
        say = ("the framing never changes: no camera move or cut in the whole film" if everything else
               "the framing holds still (no camera move or cut)") + (" (the scene has no frame/camera)" if whole else "")
        out.append({"kind": "framing_held", "start": t0, "end": t1, "text": f"{_span(t0, t1)}: {say}"})
    return out


def pose_vectors(doc_data: dict, comp: dict, times: list[float]) -> tuple[dict[str, list], list[str]]:
    """{rig id: per time the centres of its parts relative to its body box, in body heights (None where not measured)}."""
    from rostrum2d import placement
    rigs = {k: v for k, v in edge_cut.rig_parts(comp).items() if v}
    if not rigs:
        return {}, []
    ask, out, notes = placement.asker(doc_data, comp["id"], (min(times), max(times))), {}, []
    for rid, ids in rigs.items():
        found, bad = [], set()
        for t in times:
            got = _centres(ask, t, [i for i in ids if i not in bad], placement)
            if len(got) < len(ids) - len(bad):          # some part fell out: remember it, so the next asks stay whole
                bad |= {i for i in ids if i not in got and i not in bad}
            found.append(got)
        common = [i for i in ids if sum(i in f for f in found) >= 0.9 * len(found)]   # swapped mouths and eyes come and go: leave them out
        if not common:
            notes.append(f'rig "{rid}": no part is drawn through the film, so its pose was not measured')
            continue
        rows = []
        for f in found:
            cs = {i: f[i] for i in common if i in f}
            if len(cs) < len(common) * 0.9:
                rows.append(None)
                continue
            ys, xs = [c[1] for c in cs.values()], [c[0] for c in cs.values()]
            h = max(max(ys) - min(ys), 1.0)
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            rows.append({i: ((x - mx) / h, (y - my) / h) for i, (x, y) in cs.items()})
        out[rid] = rows
    return out, notes


def _centres(ask, t: float, ids: list[str], placement) -> dict:
    """{part id: its centre in comp px} at t; a part the engine refuses (not drawn then) is left out."""
    places = edge_cut.ask_drawn(ask, t, ids)
    return {i: placement.comp_point(p, p["w"] / 2, p["h"] / 2) for i, p in places.items() if p.get("w") and p.get("h")}


def _pose_moved(a: dict | None, b: dict | None) -> float:
    if a is None or b is None:
        return 1.0
    both = a.keys() & b.keys()
    return max((abs(a[i][0] - b[i][0]) + abs(a[i][1] - b[i][1]) for i in both), default=1.0)


def poses(vectors: dict[str, list], times: list[float], step: float) -> list[dict]:
    """Stretches of HOLD_POSE_S or more where a character's parts barely move against its own body (a walk, a gesture or a
    turn all show; a slide across the picture or a breath does not)."""
    out = []
    for rid, rows in vectors.items():
        held, anchor = [], None
        for r in rows:
            held.append(anchor is not None and _pose_moved(anchor, r) < POSE_SAME)
            if not held[-1]:
                anchor = r
        held = [h or (i + 1 < len(held) and held[i + 1]) for i, h in enumerate(held)]
        for t0, t1, _, _ in _runs(times, held, step, HOLD_POSE_S):
            out.append({"kind": "pose_held", "start": t0, "end": t1, "id": rid,
                        "text": f'{_span(t0, t1)}: character "{rid}" barely changes pose for {t1 - t0:g} s (its limbs move under {round(POSE_SAME * 100)} % of its height)'})
    return out


def _visible(n: dict) -> bool:
    x0, y0, x1, y1 = drawn_box(n)
    return n["in_time"] and n["opacity"] > 0.02 and (x1 - x0) * (y1 - y0) > 4


def _overlap(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])) or 1.0
    return max(0.0, w) * max(0.0, h) / small


def layer_facts(comp: dict, times: list[float], step: float) -> list[dict]:
    """Titles touching the frame edge, faint old headings behind new ones, and sets of parts not showing in a showing group."""
    W, H = comp_size(comp)
    edge, ghost, hollow, shown = {}, {}, {}, {}
    for t in times:
        nodes = flatten(comp, t)
        texts = [n for n in nodes if n["type"] == "text" and _visible(n)]
        for n in texts:
            x0, y0, x1, y1 = drawn_box(n)
            mx, my = EDGE_CUT * (x1 - x0), EDGE_CUT * (y1 - y0)
            sides = [s for s, hit in (("left", x0 < -mx), ("right", x1 > W + mx), ("top", y0 < -my), ("bottom", y1 > H + my)) if hit]
            if sides and n["opacity"] >= SHOWN and x1 > 0 and y1 > 0 and x0 < W and y0 < H:
                edge.setdefault((n["id"], sides[0]), []).append((t, y1 - y0))
        for f in texts:
            if FAINT[0] <= f["opacity"] <= FAINT[1]:
                for s in texts:
                    if s is not f and s["opacity"] >= 0.7 and _overlap(drawn_box(f), drawn_box(s)) > 0.3:
                        ghost.setdefault((f["id"], s["id"]), []).append((t, f["opacity"]))
        kids: dict[str, list[dict]] = {}
        for n in nodes:
            kids.setdefault(n["within"][-1] if n["within"] else "", []).append(n)
        for parent, ns in kids.items():
            sets: dict[str, list[dict]] = {}
            for n in ns:
                sets.setdefault(stem(n["id"]), []).append(n)
            rest = any(_visible(n) for n in ns if len(sets[stem(n["id"])]) < SET_MIN)
            for st, members in sets.items():
                if parent and len(members) >= SET_MIN:
                    if any(_visible(n) for n in members):
                        shown.setdefault((parent, st), t)
                    elif rest and (parent, st) not in shown:     # before the set first shows: not drawn in yet
                        hollow.setdefault((parent, st), []).append(t)
    out = []
    spans: dict[tuple, list] = {}           # texts cut over the same stretch are one line, the tallest (a title) named first
    for (lid, side), rows in edge.items():
        for t0, t1, _, _ in _spans([r[0] for r in rows], step, 0):
            spans.setdefault((t0, t1), []).append((max(h for t, h in rows if t0 <= t <= t1), lid, side))
    for (t0, t1), hits in spans.items():
        hits.sort(reverse=True)
        who = f'text "{hits[0][1]}" is' if len(hits) == 1 else f'{len(hits)} texts ({", ".join(chr(34) + h[1] + chr(34) for h in hits[:3])}{" …" if len(hits) > 3 else ""}) are'
        out.append({"kind": "text_edge", "start": t0, "end": t1, "id": hits[0][1], "ids": [h[1] for h in hits], "height_px": round(hits[0][0]),
                    "text": f'{_at(t0, t1, step)}: {who} cut off by the {hits[0][2]} edge of the frame'})
    for (faint, over), rows in ghost.items():
        for t0, t1, _, _ in _spans([r[0] for r in rows], step, GHOST_S):
            pct = round(100 * max(o for t, o in rows if t0 <= t <= t1))
            out.append({"kind": "ghost_text", "start": t0, "end": t1, "id": faint,
                        "text": f'{_span(t0, t1)}: text "{faint}" still shows faintly (up to {pct} % opacity) behind "{over}"'})
    for (parent, st), ts in hollow.items():
        for t0, t1, _, _ in _spans(ts, step, HOLLOW_S):
            where = f'in group "{parent}"' if parent else "in the scene"
            out.append({"kind": "set_hidden", "start": t0, "end": t1, "id": st,
                        "text": f'{_span(t0, t1)}: none of the {st.replace("#", "*")} parts {where} shows while the rest does (bars or items not drawn in yet?)'})
    return out


def _spans(ts: list[float], step: float, least: float):
    """Runs of sample times one step apart, as _runs gives them."""
    if not ts:
        return []
    grid = [round(t, 6) for t in ts]
    flags_t = sorted(set(grid))
    out, a = [], flags_t[0]
    for prev, t in zip(flags_t, flags_t[1:] + [None]):
        if t is None or t - prev > step * 1.5:
            if prev + step - a >= least - 1e-9:
                out.append((round(a, 2), round(prev + step, 2), 0, 0))
            a = t
    return out


def _at(t0: float, t1: float, step: float) -> str:
    return f"{t0:g} s" if t1 - t0 <= step + 1e-9 else _span(t0, t1)
