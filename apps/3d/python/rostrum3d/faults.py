"""The document faults of a shot that the picture checks (mcp/shot_faults.py: dark, blown, cut_edge, out_of_frame, floating,
sinking) can't see, as notes of the same list (rostrum_core/mcp/faults.py: {id, what, when}), given only when the agent asks with
`notes: true`; they never change a reply or hold back a render (round 4 of the 3D gaps: judges cap a piece for these):

  separated:<part>      a part of a figure (two shapes grouped together or sunk into each other at the shot's start) that later
                        has a gap to the body;
  leaves_frame:<item>   a subject in the picture that later goes wholly out of it (shot_faults judges one cut on a frame, or out
                        on every frame);
  cut_edge:<cloth|copies>  a cloth's simulated points, or falling copies where they land, on or past the frame edge (sim/sim_faults.py:
                        the shape boxes don't follow a simulation, so these replace shot_faults' entry of the same id);
  no_floor:<shot>       no ground or floor anywhere in the picture: whatever stands has no ground under it (round 5: Hello r1);
  backdrop_edge:<dome>  a sky photo the camera sees shows past the floor, its room's edges across the shot (backdrop.py);
  through_body:<clay>.<joint> / off_body:<item> / reads_still:<clay>.<joint>  a posed figure's part through another, a feature
                        sliding off it, a keyed swing too small to see (pose_faults.py); on_rim:<item> a feature seen on the
                        outline of the part it sits on, reading as beside it (pose_rim.py); touches_body:<clay>.<joint> a part
                        meeting another on the picture (pose_touch.py); face_unmatched:<a>~<b> a pair of eyes unlike in size, height or as
                        seen (pose_face.py); wave_small / wave_in_step:<clay>.<joint> a swing too small on screen or in step
                        with stills one second apart (pose_wave.py);
  passes_through:<a>~<b>  two things not built as one sunk into each other deeper than 1 cm, by their real forms (contact_faults.py);
  frozen_end:<shot>     the shot's last 2 s or more with nothing moving at all (still_faults.py; whole-shot checks only, never
                        one frame's look or a still render).

Read from the document as look_motion reads it (motion_track.Track, falls where the stored simulation has them), on about SAMPLES
frames of the shot (look_frame: the frame and its neighbours): nothing is rendered.
"""
from __future__ import annotations

import re

from rostrum_core.mcp import faults as F

from .backdrop import backdrop_edge
from .contact_faults import contact_faults
from .motion_track import Camera, Track
from .pose_faults import pose_faults
from .still_faults import frozen_end

SAMPLES = 10            # frames looked at over a shot (look_frame: the frame and its neighbours)
TOUCH_M = 0.005         # boxes closer than this touch
SINK_M = 0.002          # boxes sunk into each other deeper than this are one figure
GAP_M = 0.01            # a gap smaller than this is not seen
BIG_M = 3.0             # this long or more: a floor, wall or backdrop
EDGE = 0.01             # share of the picture a box may pass its edge by before it counts as past it
RAYS = 7                # the floor test: RAYS × RAYS points over the picture
_BACK = re.compile(r"ground|floor|wall|sky|backdrop|cyc|room|stage|table_?top|plinth_?top", re.I)
_FLOOR = re.compile(r"ground|floor|backdrop|cyc|stage|table|plinth|rug|carpet", re.I)
_ROUND = ("sphere", "capsule", "cylinder", "cone", "torus")


def samples(info: dict, at: int | None = None) -> list[int]:
    s0, s1 = info["start"], info["end"]
    if at is not None:
        return sorted({s0, max(at - 1, s0), at, min(at + 1, s1)})
    n = min(SAMPLES, s1 - s0 + 1)
    return sorted({round(s0 + (s1 - s0) * i / max(n - 1, 1)) for i in range(n)})


def when(info: dict, f: int) -> str:
    return f"frame {f}, {(f - info['start']) / info['fps']:.2f} s"


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
    """A box's corners; a round shape's or a clay's 6 extreme points (its box's corners stick out past a ball)."""
    item = track.fr.items[id_]
    lo, hi = _box(solid)
    if item["type"] == "clay" or item.get("shape") in _ROUND:
        mid = [(lo[k] + hi[k]) / 2 for k in range(3)]
        return [[(lo, hi)[s][k] if k == a else mid[k] for k in range(3)] for a in range(3) for s in (0, 1)]
    return solid[0]


def _linked(track: Track, a: str, b: str) -> bool:
    """Built as one: under the same parent, or one the other's parent."""
    pa, pb = track.fr.parent.get(a), track.fr.parent.get(b)
    return (pa is not None and pa == pb) or pa == b or pb == a


def doc_faults(data: dict, info: dict, folder=None, at: int | None = None, track: Track | None = None) -> list[dict]:
    """The notes; [] when nothing was measured or the shot can't be measured (a check never breaks its reply)."""
    from .mcp import motion_sim
    fs = samples(info, at)
    try:
        sim = motion_sim.moves(data, info, folder)
        if track is None or not all(f in track.cams for f in fs):
            track = Track(data, info, range(fs[0], fs[-1] + 1), folder, sim)
        found = _faults(track, info, fs, at)
    except Exception:  # noqa: BLE001
        return []
    try:                                                   # a whole-shot fault: not on one frame's look or a still render
        found += frozen_end(data, info, folder, sim, track.fr) if at is None else []
    except Exception:  # noqa: BLE001
        pass
    try:
        from .sim.sim_faults import sim_faults
        found += sim_faults(data, info, folder, fs, at)
    except Exception:  # noqa: BLE001
        pass
    return found


def _faults(track: Track, info: dict, fs: list[int], at: int | None) -> list[dict]:
    boxes: dict[str, dict[int, tuple]] = {}
    for id_ in track.ids():
        if id_ in track.skipped or track.fr.items[id_]["type"] not in ("mesh", "combine", "clay"):
            continue
        rows = {f: track.row(id_, f) for f in fs}
        if all(r["solid"] and r["shown"] for r in rows.values()):
            boxes[id_] = {f: (_box(r["solid"]), r["solid"]) for f, r in rows.items()}
    if not boxes:
        return []
    s0, w, h = fs[0], info["width"], info["height"]
    back = {i for i, b in boxes.items() if track.fr.items[i].get("shape") in ("plane", "disc") or _size(b[s0][0]) >= BIG_M
            or _BACK.search(i) or _BACK.search(track.fr.items[i].get("name") or "")}
    for i in set(boxes) - back:                          # a set piece wider or taller than the picture is framing, not a subject
        pts = [p for p in (track.cams[s0].project(q) for q in boxes[i][s0][1][0]) if p] if s0 in track.cams else []
        if pts and (max(x for x, _ in pts) - min(x for x, _ in pts) > w or max(y for _, y in pts) - min(y for _, y in pts) > h):
            back.add(i)
    subj = [i for i in boxes if i not in back]
    check = [at] if at is not None else fs
    return _separations(track, info, boxes, subj, s0, check) + _leaving(track, info, boxes, subj, fs, check) + \
        _no_floor(track, info, boxes, back, subj, check) + backdrop_edge(track, info, boxes, check) + \
        pose_faults(track, info, check) + _contacts(track, info, check)


def _contacts(track, info, check) -> list[dict]:
    try:
        return contact_faults(track, info, check)
    except Exception:  # noqa: BLE001
        return []


def _separations(track, info, boxes, subj, s0, check) -> list[dict]:
    out = []
    for n, a in enumerate(subj):
        for b in subj[n + 1:]:
            g0 = _gap(boxes[a][s0][0], boxes[b][s0][0])
            if not (g0 < -SINK_M or (g0 <= TOUCH_M and _linked(track, a, b))):
                continue
            small, big = sorted((a, b), key=lambda i: _size(boxes[i][s0][0]))
            limit = max(GAP_M, 0.1 * _size(boxes[small][s0][0]))
            f = next((f for f in check if _gap(boxes[a][f][0], boxes[b][f][0]) > limit), None)
            if f is not None and not any(x["id"] == f"separated:{small}" for x in out):
                g = _gap(boxes[a][f][0], boxes[b][f][0])
                out.append(F.note(f"separated:{small}", f"part {small} comes apart from {big}: a {g * 100:.0f} cm gap "
                                  f"(they {'were joined' if g0 < -SINK_M else 'touched'} at the start)", when(info, f)))
    return out


def _leaving(track, info, boxes, subj, fs, check) -> list[dict]:
    out = []
    for i in subj:
        if not any(boxes[i][f][0] != boxes[i][fs[0]][0] for f in fs):
            continue                                       # a still thing out of the picture: shot_faults' out_of_frame
        seen = {f: edges(track.cams[f], _points(track, i, boxes[i][f][1])) for f in check if f in track.cams}
        first_in = min((f for f, s in seen.items() if s[0] != "out"), default=None)
        gone = next((f for f, s in sorted(seen.items()) if s[0] == "out" and first_in is not None and f > first_in), None)
        if gone is not None:
            out.append(F.note(f"leaves_frame:{i}", f"{i} leaves the picture ({', '.join(seen[gone][1]) or 'behind the camera'})",
                              when(info, gone)))
    return out


def _no_floor(track, info, boxes, back, subj, check) -> list[dict]:
    """No ground in the picture: rays through a grid of the picture never reach a floor's top (a ground/backdrop/table-named
    thing, or a flat one under the subjects). Only for a shot with something standing in it."""
    if not subj:
        return []
    f = check[len(check) // 2]
    cam = track.cams.get(f)
    lows = [boxes[i][f][0][0][1] for i in subj]
    floors = [boxes[i][f][0] for i in back if (_FLOOR.search(i) or boxes[i][f][0][1][1] - boxes[i][f][0][0][1] < 0.05)
              and boxes[i][f][0][1][1] <= min(lows) + GAP_M]
    if cam is None or not floors:
        return []
    for a in range(RAYS):
        for b in range(RAYS):
            u, v = -1 + 2 * (a + 0.5) / RAYS, 1 - 2 * (b + 0.5) / RAYS
            d = [-cam.back[k] + u * cam.tan_w * cam.right[k] + v * cam.tan_h * cam.up[k] for k in range(3)]
            for lo, hi in floors:
                if abs(d[1]) < 1e-9 or (t := (hi[1] - cam.eye[1]) / d[1]) <= 0:
                    continue
                x, z = cam.eye[0] + t * d[0], cam.eye[2] + t * d[2]
                if lo[0] <= x <= hi[0] and lo[2] <= z <= hi[2]:
                    return []
    return [F.note(f"no_floor:{info['id']}", "no floor or ground anywhere in the picture: what stands in it has no ground "
                   "under it and no contact shadow", when(info, f))]
