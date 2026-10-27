"""A clay's detail (the size of its smallest grain, the core's voxel size) when it follows the camera (SPEC § 3.3,
CONTRACT CL2): about one grain per 1.5 pixels at the closest shot that sees the clay, so a creature far away in every
shot costs little and one in a close-up gets fine detail.

For each shot with a camera, at a few frames spread over the shot (its ends and up to 7 between), the clay's bounds
(a sphere round its pieces' `at` / `to` and radius, mirrored copies included, through the clay's world transform;
strokes are left out: they stay near the pieces) are tested against the camera's view. Where the camera sees them, one
pixel at the clay's nearest point is distance × sensor width / (focal length × shot width) wide. The smallest of
those × 1.5, rounded to 0.1 mm and kept within 0.2 mm .. 5 cm and no finer than the clay's size allows
(MOST_GRAINS), is the detail; no shot sees the clay → the CL1 rule, its radius / 100. Rounding is what keeps it
stable: a camera moving changes the clay (and its cache key) only when the rounded number changes. Plain Python, a
few dozen transforms per clay.
"""
from __future__ import annotations

import math

from . import aim, clay_shapes
from .resolve import Frames

GRAIN_PX, LO, HI, ROUND = 1.5, 0.0002, 0.05, 4        # grain per pixel; clamp (m); round to 0.1 mm
SAMPLES = 9                                           # frames tested per shot, its first and last included
# CL7b: the most grains a clay's box (round its pieces, generous) may hold at the detail the shots ask for. The core
# builds a drawn shape in one box of grains (7 buffers of 4 bytes each): a 48 cm pear seen close up asked for 0.2 mm,
# 18 billion grains, and the core failed with "bad allocation". This box is generous (an outline's points get its
# whole thickness): the core's own is about a third of it, so 64 million here is roughly 0.5 GB of work there.
MOST_GRAINS = 64e6


def floor_for(item: dict) -> float:
    """The finest detail the clay's box allows (MOST_GRAINS), rounded up to 0.1 mm; 0 for a clay with no pieces."""
    own = balls(item)
    if not own:
        return 0.0
    lo, hi = _box(own)
    vol = math.prod(max(b - a, 1e-6) for a, b in zip(lo, hi))
    return math.ceil((vol / MOST_GRAINS) ** (1 / 3) * 1e4) / 1e4


def _clamp(v: float) -> float:
    return max(LO, min(HI, round(v, ROUND)))


def bounds(item: dict) -> tuple[list[float], float] | None:
    """(centre, radius) in the clay's own space of a sphere round its added pieces (all pieces when none adds);
    None for a clay with no pieces."""
    own = balls(item)
    if not own:
        return None
    lo, hi = _box(own)
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    return centre, max(math.dist(centre, p) + r for p, r in own)


def _box(bs):
    return [min(p[i] - r for p, r in bs) for i in range(3)], [max(p[i] + r for p, r in bs) for i in range(3)]


def balls(item: dict) -> list:
    """[(centre, radius), …] in the clay's own space round its added pieces (all pieces when none adds), mirrored
    pieces on both sides: what `bounds` measures a clay by (generous: an outline's points get its whole thickness)."""
    pieces = [s for s in item.get("steps", []) if s.get("step") == "piece" and not s.get("hidden")
              and (s.get("at") or s.get("plane"))]
    pieces = [s for s in pieces if s.get("mode", "add") == "add"] or pieces
    if not pieces:
        return []
    out = []
    for s in pieces:
        if s.get("plane"):                                            # drawn or spun (CL3): balls round its points
            own = clay_shapes.balls(s)
        else:
            ends = [s["at"]] + ([s["to"]] if s.get("shape") == "capsule" and s.get("to") else [])
            own = [(p, s.get("radius", 0.1)) for p in ends]
        if s.get("symmetry") == "x":
            own += [([-p[0], p[1], p[2]], r) for p, r in own]
        out += [([float(v) for v in p], float(r)) for p, r in own]
    return out


def reach(item: dict) -> list[list[float]]:
    """Points in the clay's own space that reach as far as its added pieces do (all pieces when none adds), mirrored
    pieces on both sides: what framing measures a clay by (item_bounds). Tighter than `balls`, which stay generous
    for the detail rule."""
    pieces = [s for s in item.get("steps", []) if s.get("step") == "piece" and not s.get("hidden")
              and (s.get("at") or s.get("plane"))]
    pieces = [s for s in pieces if s.get("mode", "add") == "add"] or pieces
    out = []
    for s in pieces:
        if s.get("plane"):
            own = clay_shapes.reach(s)
        else:
            r = s.get("radius", 0.1)
            ends = [s["at"]] + ([s["to"]] if s.get("shape") == "capsule" and s.get("to") else [])
            own = [[c[k] + (sg * r if k == axis else 0.0) for k in range(3)] for c in ends for axis in range(3) for sg in (-1.0, 1.0)]
        if s.get("symmetry") == "x":
            own += [[-p[0], p[1], p[2]] for p in own]
        out += [[float(x) for x in p] for p in own]
    return out


def _frames(start: int, end: int) -> list[int]:
    n = min(SAMPLES, end - start + 1)
    return sorted({start + round(i * (end - start) / (n - 1)) for i in range(n)}) if n > 1 else [start]


def _sees(p: list[float], r: float, tan_w: float, tan_h: float, near: float, far: float) -> bool:
    """Does a camera (looking down its −Z, half-view tangents tan_w, tan_h) see a sphere at p (camera space)?"""
    x, y, z = p
    depth = -z
    if depth + r < near or depth - r > far:
        return False
    return (abs(x) - tan_w * depth <= r * math.hypot(1.0, tan_w)
            and abs(y) - tan_h * depth <= r * math.hypot(1.0, tan_h))


def _pixel(fr: Frames, cam: str, clay: str, f: int, ball, width: int, height: int) -> float | None:
    """One pixel's world size at the clay's nearest point, when the camera sees the clay at frame f."""
    cv, cw, w = fr.values(cam, f), fr.world(cam, f), fr.world(clay, f)
    centre = aim.point(w, ball[0])
    r = ball[1] * max(math.hypot(*(w[0][i][j] for i in range(3))) for j in range(3))   # its largest scale
    p = aim.point(aim.invert(cw), centre)
    tan_w = cv["sensorWidth"] / (2 * cv["focalLength"])
    if not _sees(p, r, tan_w, tan_w * height / width, cv["near"], cv["far"]):
        return None
    nearest = max(-p[2] - r, cv["near"])
    return nearest * cv["sensorWidth"] / (cv["focalLength"] * width)


def auto(data: dict, item: dict, folder=None) -> float | None:
    """The detail worked out from the document's shots; None when no shot's camera sees the clay."""
    ball = bounds(item)
    if ball is None:
        return None
    items = {}
    stack = list(data.get("items", []))
    while stack:
        it = stack.pop()
        items[it["id"]] = it
        stack += it.get("children", [])
    best = math.inf
    for shot in data.get("shots", []):
        cam, fps = shot.get("camera"), shot.get("fps", 24)
        if not cam or items.get(cam, {}).get("type") != "camera":
            continue
        start, end = round(shot.get("start", 0.0) * fps), round(shot.get("end", 2.0) * fps) - 1
        if end < start:
            continue
        fr = Frames(data, range(start, end + 1), fps, folder)
        for f in _frames(start, end):
            px = _pixel(fr, cam, item["id"], f, ball, shot.get("width", 1920), shot.get("height", 1080))
            if px is not None:
                best = min(best, px)
    return None if best == math.inf else max(_clamp(GRAIN_PX * best), floor_for(item))


def held(data: dict, item: dict, folder=None) -> str:
    """A plain sentence when the shots ask for a finer detail than the clay's size allows (MOST_GRAINS), else ""."""
    if item.get("detailMode", "auto") == "fixed":
        return ""
    ball = bounds(item)
    found = auto(data, item, folder)
    if ball is None or found is None:
        return ""
    floor = floor_for(item)
    if found > floor:
        return ""
    # what the shots ask for, without the floor (auto with it lifted)
    asked = _asked(data, item, folder)
    if asked is None or asked >= floor:
        return ""
    lo, hi = _box(balls(item))
    gb = math.prod(max(b - a, 1e-6) for a, b in zip(lo, hi)) / asked ** 3 * 28 / 1e9  # (generous box)
    return (f"Detail held at {floor * 1e3:g} mm: the closest shot asks for {asked * 1e3:g} mm, which would need "
            f"about {gb / 3:.0f} GB for this clay. Set Detail to Fixed to choose it yourself.")


def _asked(data: dict, item: dict, folder=None) -> float | None:
    global MOST_GRAINS
    keep = MOST_GRAINS
    MOST_GRAINS = math.inf
    try:
        return auto(data, item, folder)
    finally:
        MOST_GRAINS = keep


def detail(data: dict, item: dict, folder=None) -> float:
    """The detail the core builds the clay at: `detail` as typed when Fixed; else worked out from the shots, or its
    radius / 100 when no shot sees it."""
    if item.get("detailMode", "auto") == "fixed":
        return float(item["detail"])
    found = auto(data, item, folder)
    if found is not None:
        return found
    ball = bounds(item)
    return _clamp(ball[1] / 100) if ball else float(item.get("detail", 0.002))
