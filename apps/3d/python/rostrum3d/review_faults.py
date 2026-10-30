"""Review notes a 3D agent asks for with `notes: true` (3D review notes, 2026-10-30; 2D's review notes are the model), in
the shot's one list (faults.py): measured from the document, never judged, never a fix. Anything here can be meant.

  camera_inside:<item>   the shot camera inside a shape or touching it (under CAM_M from its surface; a fixed form by its
                         exact surface, a clay or another mesh by its box), or under the ground;
  empty_frame:<shot>     the subjects cover under EMPTY of the picture (by their outlines' boxes, so it is at most this);
  fills_frame:<item>     one subject's outline box covers over FULL of the picture;
  lands_above:<item> / lands_in:<item>
                         a thing that comes down (its lowest point falls LAND_DROP_M or more within half a second) and stops
                         with that point over LAND_M above what is under it, or over LAND_M into it;
  slides:<item>          a thing touching what it stands on (within CONTACT_M) for at least CONTACT_F frames whose footprint
                         gets over SLIDE_M from where it touched down, not rolling (a round shape turning by about the travel is rolling);
  slides:<clay>.<joint>  a figure's foot (a joint named foot, toe, heel or sole) planted (at its lowest nearby, hardly moving
                         up or down) while it gets over SLIDE_M from where it was planted;
  not_measured:<shot>    what these checks could not measure, so an empty list is never an all-clear.

Landings and slides read every frame of the shot (whole-shot looks only: look_sheet, look_motion, render_video); the others
the sampled frames. Nothing is rendered.
"""
from __future__ import annotations

import math
import re

from rostrum_core.mcp import faults as F

from . import skin
from .contact_faults import FORMS, placed

CAM_M = 0.01             # the camera this close to a surface touches it
EMPTY = 0.05             # subjects covering less of the picture than this: mostly empty
FULL = 0.85              # one subject covering more of the picture than this: mostly that one thing
GRID = (48, 27)          # cells the picture is split into to add the subjects' boxes up
LAND_M = 0.01            # a landing this far above / into what is under it
LAND_DROP_M = 0.02       # … after coming down at least this far within LAND_S
LAND_S = 0.5
CONTACT_M = 0.01         # touching what it stands on: the lowest point within this of its top
CONTACT_F = 3            # frames in contact before a slide counts
SLIDE_M = 0.02           # travel along the ground while touching it
ROLL = 0.5               # turned by at least this share of travel / radius: rolling, not sliding
FOOT_STILL_M = 0.003     # a planted foot moves up or down less than this a frame
_FOOT = re.compile(r"foot|feet|toe|heel|sole", re.I)
_ROUND = ("sphere", "cylinder", "capsule", "torus")
_TILTED = ("cylinder", "capsule", "cone", "torus")


def when(info: dict, f: int) -> str:
    return f"frame {f}, {(f - info['start']) / info['fps']:.2f} s"


def _secs(info: dict, f: int) -> str:
    return f"{(f - info['start']) / info['fps']:.1f} s"


# --- the camera ------------------------------------------------------------------------------------------------------

def _in_box(solid, p, pad: float) -> float | None:
    """How far p is inside an oriented box (corners, axes), as a distance to its nearest face (negative: outside by
    at least that much); None when p is further than `pad` outside."""
    corners, axes = solid
    inside = math.inf
    for ax in axes:
        n = math.hypot(*ax) or 1.0
        u = [c / n for c in ax]
        d = [sum(c[k] * u[k] for k in range(3)) for c in corners]
        x = sum(p[k] * u[k] for k in range(3))
        inside = min(inside, x - min(d), max(d) - x)
    return inside if inside >= -pad else None


def camera_inside(track, info: dict, boxes: dict, back: set, check: list[int]) -> list[dict]:
    out, seen = [], set()
    for f in check:
        cam = track.cams.get(f)
        if cam is None:
            continue
        eye = cam.eye
        for i, per in boxes.items():
            if i in seen or f not in per:
                continue
            (lo, hi), solid = per[f]
            if i in back and hi[1] - lo[1] < 0.05:          # a floor: under it, not inside it
                if lo[0] <= eye[0] <= hi[0] and lo[2] <= eye[2] <= hi[2] and eye[1] < hi[1] - CAM_M:
                    seen.add(i)
                    out.append(F.note(f"camera_inside:{i}", f"the camera is {(hi[1] - eye[1]) * 100:.0f} cm under {i}'s top "
                                      f"(camera at y = {eye[1]:.3f})", when(info, f)))
                continue
            form = placed(track.fr, i, f)
            d = -form.dist(eye) if form else _in_box(solid, eye, CAM_M)
            if d is None or d < -CAM_M:
                continue
            seen.add(i)
            how = "exact form" if form else "box"
            out.append(F.note(f"camera_inside:{i}", (f"the camera is inside {i}, {d * 100:.1f} cm in (by its {how})" if d > 0 else
                                                     f"the camera touches {i}: {-d * 100:.1f} cm from its surface (by its {how})"),
                              when(info, f)))
    return out


# --- how full the picture is ------------------------------------------------------------------------------------------

def _rect(cam, pts):
    seen = [p for p in (cam.project(q) for q in pts) if p]
    if not seen or len(seen) < len(pts):
        return None
    x0, x1 = max(0.0, min(x for x, _ in seen)), min(cam.w, max(x for x, _ in seen))
    y0, y1 = max(0.0, min(y for _, y in seen)), min(cam.h, max(y for _, y in seen))
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def framing(track, info: dict, boxes: dict, subj: list[str], points, check: list[int]) -> list[dict]:
    """empty_frame / fills_frame on the sampled frames; `points(id, solid)`: the world points that outline a shape."""
    if not subj:
        return []
    empty, full = [], {}
    gw, gh = GRID
    for f in check:
        cam = track.cams.get(f)
        if cam is None:
            continue
        rects = {i: r for i in subj if f in boxes[i] and (r := _rect(cam, points(track, i, boxes[i][f][1])))}
        cells = set()
        for i, (x0, y0, x1, y1) in rects.items():
            a = (x1 - x0) * (y1 - y0) / (cam.w * cam.h)
            if a > FULL:
                full.setdefault(i, (f, a))
            cells |= {(u, v) for u in range(int(x0 / cam.w * gw), math.ceil(x1 / cam.w * gw))
                      for v in range(int(y0 / cam.h * gh), math.ceil(y1 / cam.h * gh))}
        share = len(cells) / (gw * gh)
        if share < EMPTY:
            empty.append((f, share))
    out = []
    if empty:
        f, share = empty[0]
        at = ", ".join(_secs(info, g) for g, _ in empty[:6]) + (" …" if len(empty) > 6 else "")
        out.append(F.note(f"empty_frame:{info['id']}", f"the subjects cover about {share * 100:.0f} % of the picture or less "
                          f"(their outlines' boxes) at {len(empty)} of {len(check)} sampled frames: {at}", when(info, f)))
    for i, (f, a) in full.items():
        out.append(F.note(f"fills_frame:{i}", f"{i} fills {min(a, 1.0) * 100:.0f} % of the picture (its outline's box)", when(info, f)))
    return out


# --- landings and slides ------------------------------------------------------------------------------------------------

def _low(track, i: str, f: int, solid) -> float:
    """Its lowest point: a turned cylinder, capsule, cone or torus by its surface (its box's corner reaches lower), else its box."""
    upright = abs(solid[1][1][1]) >= 0.9999 * (math.hypot(*solid[1][1]) or 1.0)     # its own up is the world's: its box's floor is exact
    form = placed(track.fr, i, f) if track.fr.items[i].get("shape") in _TILTED and not upright else None
    return form.lo[1] if form else min(c[1] for c in solid[0])


def _turned(a, b) -> float:
    """The angle (radians) between two world transforms' turns."""
    def cols(m):
        c = [[row[k] for row in m[0]] for k in range(3)]
        return [[x / (math.hypot(*v) or 1.0) for x in v] for v in c]
    ca, cb = cols(a), cols(b)
    tr = sum(sum(ca[k][j] * cb[k][j] for j in range(3)) for k in range(3))
    return math.acos(max(-1.0, min(1.0, (tr - 1) / 2)))


def _support(me: str, lo, hi, low: float, statics: dict, ground: float) -> tuple[str | None, float]:
    """(what is under the footprint, its top): the highest other shape whose box spans the footprint and whose top is
    under the middle of `me`; the ground when nothing is."""
    mid = (low + hi[1]) / 2
    best = (None, ground)
    for j, (a, b) in statics.items():
        if j != me and a[0] < hi[0] and lo[0] < b[0] and a[2] < hi[2] and lo[2] < b[2] and best[1] < b[1] <= mid:
            best = (j, b[1])
    return best


def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    out, a = [], None
    for k, on in enumerate(flags + [False]):
        if on and a is None:
            a = k
        elif not on and a is not None:
            out.append((a, k - 1))
            a = None
    return out


def _travel(pts) -> float:
    """How far along the ground it gets from where it was (a sway back and forth adds nothing)."""
    return max(math.hypot(p[0] - pts[0][0], p[2] - pts[0][2]) for p in pts)


def _moving(pts, a: int, b: int) -> tuple[int, int]:
    """The first and last index in a..b where it has moved since the index before (where the slide happens)."""
    moved = [k for k in range(a + 1, b + 1) if math.hypot(pts[k][0] - pts[k - 1][0], pts[k][2] - pts[k - 1][2]) > 1e-4]
    return (moved[0] - 1, moved[-1]) if moved else (a, b)


def landings(track, info: dict, boxes0: dict, back: set, ground: float) -> list[dict]:
    """lands_above / lands_in / slides for things that travel, read every frame; `boxes0`: {id: (lo, hi)} at the first frame."""
    fr, fps, frames = track.fr, info["fps"], list(range(info["start"], info["end"] + 1))
    movers = [i for i in boxes0 if i not in back and any(fr.world(i, f) != fr.world(i, frames[0]) for f in frames[:: max(1, len(frames) // 12)] + [frames[-1]])]
    statics = {i: b for i, b in boxes0.items() if i not in movers}
    out = []
    for i in movers:
        rows = [(f, track.row(i, f)) for f in frames]
        if not all(r["solid"] for _, r in rows):
            continue
        lows, under, feet = [], [], []
        for f, r in rows:
            lo = [min(c[k] for c in r["solid"][0]) for k in range(3)]
            hi = [max(c[k] for c in r["solid"][0]) for k in range(3)]
            low = _low(track, i, f, r["solid"])
            lows.append(low)
            under.append(_support(i, lo, hi, low, statics, ground))
            feet.append([(lo[0] + hi[0]) / 2, low, (lo[2] + hi[2]) / 2])
        gaps = [low - top for low, (_, top) in zip(lows, under)]
        win = max(1, round(LAND_S * fps))
        above, into = [], []
        for k in range(1, len(frames)):
            stops = k + 1 == len(frames) or lows[k + 1] >= lows[k] - 1e-6
            if lows[k] < lows[k - 1] - 1e-6 and stops and max(lows[max(0, k - win):k]) - lows[k] >= LAND_DROP_M:
                if gaps[k] > LAND_M:
                    above.append((frames[k], gaps[k], under[k][0]))
                elif gaps[k] < -LAND_M:
                    into.append((frames[k], -gaps[k], under[k][0]))
        for kind, hits, word in (("lands_above", above, "above"), ("lands_in", into, "into")):
            if hits:
                at = "; ".join(f"{m * 100:.0f} cm {word} {on or 'the ground'} at {_secs(info, f)}" for f, m, on in hits[:4])
                out.append(F.note(f"{kind}:{i}", f"{i} comes down and stops {at}" + (f" ({len(hits)} landings)" if len(hits) > 4 else ""),
                                  when(info, hits[0][0])))
        slides = []
        for a, b in _runs([g <= CONTACT_M for g in gaps]):
            if b - a + 1 < CONTACT_F or (d := _travel(feet[a:b + 1])) <= SLIDE_M:
                continue
            item = fr.items[i]
            if item.get("shape") in _ROUND:
                v = fr.values(i, frames[a])
                turn = sum(_turned(fr.world(i, frames[k - 1]), fr.world(i, frames[k])) for k in range(a + 1, b + 1))
                if turn * float(v.get("radius", 0.5)) >= ROLL * d:
                    continue                             # it rolls
            a2, b2 = _moving(feet, a, b)
            slides.append((frames[a2], frames[b2], d, under[a][0]))
        if slides:
            at = "; ".join(f"{d * 100:.0f} cm along {on or 'the ground'}, {_secs(info, f0)}–{_secs(info, f1)}" for f0, f1, d, on in slides[:3])
            out.append(F.note(f"slides:{i}", f"{i} slides while touching what it stands on: {at}" + (" …" if len(slides) > 3 else ""),
                              when(info, slides[0][0])))
    return out + _feet(track, info)


def _feet(track, info: dict) -> list[dict]:
    from .view_look import part_point
    fr, fps, frames = track.fr, info["fps"], list(range(info["start"], info["end"] + 1))
    out = []
    for i in track.ids():
        item = fr.items[i]
        if item["type"] != "clay" or not item.get("bones"):
            continue
        for bone, _ in skin.bones_of(item):
            name = bone.get("name") or ""
            if not _FOOT.search(name):
                continue
            try:
                at = part_point(fr, f"{i}.{name}")
                pts = [at(f) for f in frames]
            except Exception:  # noqa: BLE001  a joint the pose tools can't find: not measured
                continue
            win = max(1, round(LAND_S * fps))
            planted = [abs(pts[k][1] - pts[k - 1][1]) < FOOT_STILL_M and
                       pts[k][1] <= min(p[1] for p in pts[max(0, k - win):k + win + 1]) + CONTACT_M for k in range(1, len(pts))]
            spans = [(*_moving(pts, a, b + 1), d) for a, b in _runs(planted) if b - a + 1 >= CONTACT_F and (d := _travel(pts[a:b + 2])) > SLIDE_M]
            if spans:
                at_ = "; ".join(f"{d * 100:.0f} cm, {_secs(info, frames[a])}–{_secs(info, frames[b])}" for a, b, d in spans[:3])
                out.append(F.note(f"slides:{i}.{name}", f"{i}'s {name} slides while planted (at its lowest, not lifting): {at_}",
                                  when(info, frames[spans[0][0]])))
    return out


# --- what was not measured --------------------------------------------------------------------------------------------

def not_measured(track, info: dict, boxes: dict, pictures: bool, whole: bool) -> list[dict]:
    """One note naming what the checks could not measure: shapes of unknown size, shapes passing through others checked
    only for fixed forms, pictures not looked at."""
    said = []
    if track.skipped:
        said.append("no size known for " + ", ".join(sorted(track.skipped)[:6]) + (" …" if len(track.skipped) > 6 else "")
                    + " (not judged for cuts, floating, overlaps)")
    rough = sorted(i for i in boxes if track.fr.items[i]["type"] in ("clay", "combine") or
                   (track.fr.items[i]["type"] == "mesh" and track.fr.items[i].get("shape") not in FORMS and
                    track.fr.items[i].get("shape") not in ("plane", "disc")))
    if rough:
        said.append("passing through others is checked only for spheres, boxes, cylinders, cones, capsules and tori, not "
                    + ", ".join(rough[:6]) + (" …" if len(rough) > 6 else "") + " (cuts, floating and framing use their boxes)")
    if not pictures:
        said.append("no picture was looked at, so light (near-black, clipped, flat) is not measured")
    if not whole:
        said.append("landings, slides and still stretches need the whole shot (look_frame what \"sheet\" or look_motion, with notes)")
    if not said:
        return []
    return [F.note(f"not_measured:{info['id']}", "not measured: " + "; ".join(said))]


def ground_top(track, boxes: dict, back: set, f: int) -> float:
    tops = [boxes[i][f][0][1][1] for i in back if f in boxes[i] and boxes[i][f][0][1][1] - boxes[i][f][0][0][1] < 0.05]
    return max(tops) if tops else 0.0

