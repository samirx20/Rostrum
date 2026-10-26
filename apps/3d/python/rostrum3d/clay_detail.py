"""A clay's detail (the size of its smallest grain, the core's voxel size) when it follows the camera (SPEC § 3.3,
CONTRACT CL2): about one grain per 1.5 pixels at the closest shot that sees the clay, so a creature far away in every
shot costs little and one in a close-up gets fine detail.

For each shot with a camera, at a few frames spread over the shot (its ends and up to 7 between), the clay's bounds
(a sphere round its pieces' `at` / `to` and radius, mirrored copies included, through the clay's world transform;
strokes are left out: they stay near the pieces) are tested against the camera's view. Where the camera sees them, one
pixel at the clay's nearest point is distance × sensor width / (focal length × shot width) wide. The smallest of
those × 1.5, rounded to 0.1 mm and kept within 0.2 mm .. 5 cm, is the detail; no shot sees the clay → the CL1 rule,
its radius / 100. Rounding is what keeps it stable: a camera moving changes the clay (and its cache key) only when
the rounded number changes. Plain Python, a few dozen transforms per clay.
"""
from __future__ import annotations

import math

from . import aim
from .resolve import Frames

GRAIN_PX, LO, HI, ROUND = 1.5, 0.0002, 0.05, 4        # grain per pixel; clamp (m); round to 0.1 mm
SAMPLES = 9                                           # frames tested per shot, its first and last included


def _clamp(v: float) -> float:
    return max(LO, min(HI, round(v, ROUND)))


def bounds(item: dict) -> tuple[list[float], float] | None:
    """(centre, radius) in the clay's own space of a sphere round its added pieces (all pieces when none adds);
    None for a clay with no pieces."""
    pieces = [s for s in item.get("steps", []) if s.get("step") == "piece" and s.get("at")]
    pieces = [s for s in pieces if s.get("mode", "add") == "add"] or pieces
    if not pieces:
        return None
    balls = []
    for s in pieces:
        ends = [s["at"]] + ([s["to"]] if s.get("shape") == "capsule" and s.get("to") else [])
        if s.get("symmetry") == "x":
            ends += [[-p[0], p[1], p[2]] for p in ends]
        balls += [([float(v) for v in p], float(s.get("radius", 0.1))) for p in ends]
    lo = [min(p[i] - r for p, r in balls) for i in range(3)]
    hi = [max(p[i] + r for p, r in balls) for i in range(3)]
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    return centre, max(math.dist(centre, p) + r for p, r in balls)


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
    return None if best == math.inf else _clamp(GRAIN_PX * best)


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
