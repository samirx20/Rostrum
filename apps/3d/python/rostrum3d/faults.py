"""Client-visible faults of a shot, in plain words with numbers, for the look and render replies (round 4 of the 3D gaps:
judges cap a piece at 6 for one of these, and our agents never noticed them):

- a part of a figure separates from the body (two shapes grouped together or sunk into each other at the shot's start
  that later have a gap between them);
- a thing floats above the ground or the thing under it while it holds its height (resting, standing, landed);
- a main subject (moving, simulated, or a thing of fair size) is cut by the frame edge, or leaves the frame.

Read from the document as look_motion reads it (motion_track.Track, falls where the stored simulation has them), on about
SAMPLES frames of the shot: nothing is rendered. Boxes as item_bounds measures them (a ball: an upright box round it; a
clay: the box its pieces reach). Floors, walls, skies and backdrops (planes, discs, anything 3 m or more, a set piece
wider or taller than the picture) are surfaces, never subjects. Cloth and falling copies: sim/sim_faults.py.

    lines = shot_faults(doc.data, "hero", folder)                 # [] when nothing is wrong
    lines = shot_faults(doc.data, "hero", folder, at=40)          # only what is wrong at frame 40 (look_frame)
"""
from __future__ import annotations

import re

from .motion_track import Camera, Track

SAMPLES = 10            # frames looked at over a shot (look_frame: the frame and its neighbours)
TOUCH_M = 0.005         # boxes closer than this touch
SINK_M = 0.002          # boxes sunk into each other deeper than this are one figure
GAP_M = 0.01            # a gap or a float smaller than this is not seen
STILL_M = 0.003         # a bottom moving less than this between looks holds its height
BIG_M = 3.0             # this long or more: a floor, wall or backdrop
EDGE = 0.01             # share of the picture a box may pass its edge by before it counts as cut
MOST = 4                # lines at most, worst first
_BACK = re.compile(r"ground|floor|wall|sky|backdrop|cyc|room|stage|table_?top|plinth_?top", re.I)
_ROUND = ("sphere", "capsule", "cylinder", "cone", "torus")


def samples(info: dict, frames: tuple[int, int] | None = None, at: int | None = None) -> list[int]:
    s0, s1 = info["start"], info["end"]
    if at is not None:
        return sorted({s0, max(at - 1, s0), at, min(at + 1, s1)})
    a, b = frames or (s0, s1)
    n = min(SAMPLES, b - a + 1)
    return sorted({s0, *(round(a + (b - a) * i / max(n - 1, 1)) for i in range(n))})


def _box(solid):
    c = solid[0]
    return [min(p[k] for p in c) for k in range(3)], [max(p[k] for p in c) for k in range(3)]


def _gap(a, b) -> float:
    """Distance between two boxes (0 when they touch or overlap); negative: how deep they sink into each other."""
    d = [max(a[0][k] - b[1][k], b[0][k] - a[1][k]) for k in range(3)]
    out = [max(x, 0.0) for x in d]
    return sum(x * x for x in out) ** 0.5 if any(out) else max(d)


def _size(b) -> float:
    return max(b[1][k] - b[0][k] for k in range(3))


def edges(cam: Camera, pts) -> tuple[str, list[str]]:
    """('in' | 'part' | 'out', the picture edges it passes) for world points seen by the camera."""
    seen = [p for p in (cam.project(q) for q in pts) if p]
    if not seen:
        return "out", []
    tw, th = EDGE * cam.w, EDGE * cam.h
    side = {"left": [x < -tw for x, _ in seen], "right": [x > cam.w + tw for x, _ in seen],
            "top": [y < -th for _, y in seen], "bottom": [y > cam.h + th for _, y in seen]}
    if any(all(v) for v in side.values()):
        return "out", [k for k, v in side.items() if all(v)]
    cut = [k for k, v in side.items() if any(v)]
    return ("part" if cut or len(seen) < len(pts) else "in"), cut


def _points(track: Track, id_: str, solid) -> list:
    """What to test against the picture: a box's corners; a round shape's or a clay's 6 extreme points (its box's
    corners stick out past a ball by a third of its radius)."""
    item = track.fr.items[id_]
    lo, hi = _box(solid)
    if item["type"] == "clay" or item.get("shape") in _ROUND:
        mid = [(lo[k] + hi[k]) / 2 for k in range(3)]
        return [[(lo, hi)[s][k] if k == a else mid[k] for k in range(3)] for a in range(3) for s in (0, 1)]
    return solid[0]


def _when(info: dict, f: int) -> str:
    return f"{(f - info['start']) / info['fps']:.1f} s (frame {f})"


def _linked(track: Track, a: str, b: str) -> bool:
    """Built as one: under the same parent, or one the other's parent."""
    pa, pb = track.fr.parent.get(a), track.fr.parent.get(b)
    return (pa is not None and pa == pb) or pa == b or pb == a


def note(lines: list[str]) -> str:
    """The lines as one reply sentence ("" when none)."""
    return f" Faults a client would see: {' '.join(lines)}" if lines else ""


def shot_faults(data: dict, shot_id: str, folder=None, frames: tuple[int, int] | None = None, at: int | None = None,
                track: Track | None = None) -> list[str]:
    """Short warning lines, worst first (at most MOST); [] when nothing is wrong or the shot can't be measured."""
    from .compile import shot_info
    from .mcp import motion_sim
    try:
        info = shot_info(data, shot_id)
        fs = samples(info, frames, at)
        if track is None or not all(f in track.cams for f in fs):
            track = Track(data, info, range(fs[0], fs[-1] + 1), folder, motion_sim.moves(data, info, folder))
        found = _faults(track, info, fs, at)
    except Exception:  # noqa: BLE001  (a check never breaks the look or render it is part of)
        return []
    try:                                         # a check never breaks the look or render it is part of
        from .sim.sim_faults import sim_faults
        found += sim_faults(data, info, folder, fs, at)
    except Exception:  # noqa: BLE001
        pass
    return [t for _, t in sorted(found, key=lambda x: -x[0])[:MOST]]


def _faults(track: Track, info: dict, fs: list[int], at: int | None) -> list[tuple[float, str]]:
    boxes: dict[str, dict[int, tuple]] = {}
    for id_ in track.ids():
        if id_ in track.skipped or track.fr.items[id_]["type"] not in ("mesh", "combine", "clay"):
            continue
        rows = {f: track.row(id_, f) for f in fs}
        if all(r["solid"] and r["shown"] for r in rows.values()):
            boxes[id_] = {f: (_box(r["solid"]), r["solid"]) for f, r in rows.items()}
    if not boxes:
        return []
    s0 = fs[0]
    w, h = info["width"], info["height"]
    back = {i for i, b in boxes.items() if track.fr.items[i].get("shape") in ("plane", "disc") or _size(b[s0][0]) >= BIG_M
            or _BACK.search(i) or _BACK.search(track.fr.items[i].get("name") or "")}
    for i in set(boxes) - back:                          # a set piece wider or taller than the picture is framing, not a subject
        pts = [p for p in (track.cams[s0].project(q) for q in boxes[i][s0][1][0]) if p] if s0 in track.cams else []
        if pts and (max(x for x, _ in pts) - min(x for x, _ in pts) > w or max(y for _, y in pts) - min(y for _, y in pts) > h):
            back.add(i)
    subj = [i for i in boxes if i not in back]
    check = [at] if at is not None else fs
    waiting = {i for i in subj if _sim(track.fr.items[i]) and all(boxes[i][f][0] == boxes[i][s0][0] for f in fs)}
    out = _separations(track, info, boxes, subj, s0, check) + _floats(info, boxes, subj, fs, check, at, waiting)
    return out + _framing(track, info, boxes, subj, fs, check)


def _separations(track, info, boxes, subj, s0, check) -> list[tuple[float, str]]:
    out, named = [], set()
    for n, a in enumerate(subj):
        for b in subj[n + 1:]:
            g0 = _gap(boxes[a][s0][0], boxes[b][s0][0])
            if not (g0 < -SINK_M or (g0 <= TOUCH_M and _linked(track, a, b))):
                continue
            small, big = sorted((a, b), key=lambda i: _size(boxes[i][s0][0]))
            limit = max(GAP_M, 0.1 * _size(boxes[small][s0][0]))
            for f in check:
                g = _gap(boxes[a][f][0], boxes[b][f][0])
                if g > limit and small not in named:
                    named.add(small)
                    out.append((3 + g, f"Part {small} separates from {big} at {_when(info, f)}: a {g * 100:.0f} cm gap "
                                       f"between them (they {'were joined' if g0 < -SINK_M else 'touched'} at the start). "
                                       "Keep the parts joined: parent them to one moving item, key them together, or make the figure one clay."))
                    break
    return out


def _sim(item: dict) -> bool:
    from .sim.inputs import value
    try:
        return value(item, "simulate") in ("falls", "cloth")
    except (KeyError, ValueError):
        return False


def _floats(info, boxes, subj, fs, check, at, waiting) -> list[tuple[float, str]]:
    """A group of touching shapes (a figure) that touches nothing else, holds its height there, and has its lowest point
    a little above what is under it (more than GAP_M, at most 60 % of its height or 15 cm: higher reads as flying).
    A simulated thing waiting for its drop is not resting."""
    out = []
    for f in check:
        near = [g for g in (at - 1, at + 1) if g in fs] if at is not None else [fs[k] for k in (fs.index(f) - 1, fs.index(f) + 1) if 0 <= k < len(fs)]
        clusters = _clusters({i: boxes[i][f][0] for i in subj})
        for c in clusters:
            if set(c) & waiting:
                continue
            lo = min(c, key=lambda i: boxes[i][f][0][0][1])
            bottom = boxes[lo][f][0][0][1]
            if any(abs(min(boxes[i][g][0][0][1] for i in c) - bottom) > STILL_M for g in near):
                continue                                          # going up or down there: not resting
            others = [i for i in boxes if i not in c]
            if any(_gap(boxes[i][f][0], boxes[j][f][0]) <= TOUCH_M for i in c for j in others):
                continue                                          # sits on, leans on or hangs from something
            b = boxes[lo][f][0]
            under = [boxes[j][f][0][1][1] for j in others if boxes[j][f][0][1][1] <= bottom + TOUCH_M
                     and all(boxes[j][f][0][0][k] < b[1][k] and b[0][k] < boxes[j][f][0][1][k] for k in (0, 2))]
            if not under:
                continue
            gap, tall = bottom - max(under), max(boxes[i][f][0][1][1] for i in c) - bottom
            who = next(i for i in boxes if boxes[i][f][0][1][1] == max(under))
            if GAP_M < gap <= max(0.6 * tall, 0.15) and not any(lo in t for _, t in out):
                name = lo if len(c) == 1 else f"{lo} (with {', '.join(sorted(set(c) - {lo})[:3])})"
                out.append((2 + gap, f"{name} floats {gap * 100:.0f} cm above {who} at {_when(info, f)}, holding that height: "
                                     f"its shadow sits apart from it. Lower it by {gap:.3f} m so its lowest point rests on {who}."))
    return out


def _clusters(b: dict) -> list[list[str]]:
    left, out = set(b), []
    while left:
        stack, c = [left.pop()], []
        while stack:
            i = stack.pop()
            c.append(i)
            for j in [j for j in left if _gap(b[i], b[j]) <= TOUCH_M]:
                left.discard(j)
                stack.append(j)
        out.append(c)
    return out


def _framing(track, info, boxes, subj, fs, check) -> list[tuple[float, str]]:
    out = []
    for i in subj:
        moves = any(boxes[i][f][0] != boxes[i][fs[0]][0] for f in fs)
        if not moves and _size(boxes[i][fs[0]][0]) < 0.02:
            continue
        seen = {f: edges(track.cams[f], _points(track, i, boxes[i][f][1])) for f in check if f in track.cams}
        cut = [f for f, s in seen.items() if s[0] == "part"]
        gone = [f for f, s in seen.items() if s[0] == "out"]
        first_in = min((f for f, s in seen.items() if s[0] != "out"), default=None)
        if first_in is not None and any(f > first_in for f in gone):
            f = next(f for f in gone if f > first_in)
            before = [g for g in cut if g < f]
            out.append((1.5, f"{i} leaves the frame ({', '.join(seen[f][1]) or 'behind the camera'}) at {_when(info, f)}"
                             + (f", cut by the edge from {_when(info, before[0])}" if before else "") + ". "
                             "Keep it in the shot: move it or the camera, or end the shot before it goes."))
        elif cut:
            f = cut[0]
            sides = sorted({e for g in cut for e in seen[g][1]}) or ["edge"]
            out.append((1 + len(cut) / len(seen), f"{i} is cut by the frame edge ({'/'.join(sides)}) from {_when(info, f)}"
                        f" ({len(cut)} of {len(seen)} looks). Frame it whole: move it or the camera, or widen the lens."))
    return out
