"""Faults first, for a 3D shot (rostrum_core/mcp/faults.py): what the shot camera's picture and the scene's geometry say is wrong,
named before anything else in a look / render reply.

Three checks, each with a stable fault id so `keep: {id: why}` names it across re-runs:
  dark:<shot> / blown:<shot>  the picture (its pixels): mean brightness under DARK_MEAN of full, or CLIPPED_PCT % of the pixels
                              with a channel at white (facts.measure; the same numbers inspect_exposure gives).
  cut_edge:<item>             a shown shape whose projected box (through the shot camera) crosses the picture's edge while most
                              of it (>= MOST) is inside. Ground / background-sized things (backdrop, a side over BIG_M m, a box
                              over BIG_AREA times the picture) are framing, not a subject.
  floating:<item> / sinking:<item>
                              a shape whose lowest point is more than GAP_M above the ground with nothing touching it from
                              below, or more than GAP_M below the ground (the ground: the backdrop's top, else y = 0). Judged on
                              the sampled frames together: a jump or a fall is not floating, so only a gap present on every one counts.
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError
from rostrum_core.mcp import faults as F

from rostrum3d.motion_track import Track

from .facts import measure
from .shot import seconds

DARK_MEAN = 0.08          # mean display brightness (0 black – 1 white) under this: the frame is nearly black
CLIPPED_PCT = 40.0        # share of pixels with any channel at white above this: blown out
GAP_M = 0.01              # 1 cm: lowest point this far above / below the ground
MOST = 0.5                # a cut subject has at least this share of its projected box inside the picture
MIN_CUT = 0.02            # ... and at least this share outside (a pixel's worth is not a cut)
BIG_M = 8.0               # a side longer than this is a floor or a wall
BIG_AREA = 2.0            # a projected box this many pictures large is a background


def when_of(info: dict, frame: int) -> str:
    return f"frame {frame}, {seconds(info, frame):.2f} s"


def picture(png, shot: str, when: str) -> list[dict]:
    """dark / blown from a picture's pixels."""
    m = measure(Path(png))
    mean = m["luminance"]["mean"] / 255
    out = []
    if mean < DARK_MEAN:
        out.append(F.fault(f"dark:{shot}", f"the picture is nearly black: mean brightness {mean:.2f} of 1 (under {DARK_MEAN:g})",
                           "raise the key light about 2 stops (its intensity ×4) or put back the starting lights (key_light, rim_light, sky); inspect_exposure shows the numbers", when))
    if m["clipped_pct"] > CLIPPED_PCT:
        out.append(F.fault(f"blown:{shot}", f"{m['clipped_pct']:g} % of the picture is blown out to white (over {CLIPPED_PCT:g} %)",
                           "lower the lights' intensity (halve it) or the shot's Exposure; inspect_exposure shows where", when))
    return out


def _span(corners, k):
    v = [c[k] for c in corners]
    return min(v), max(v)


def _edges(x0, y0, x1, y1, w, h) -> list[str]:
    return [n for n, hit in (("left", x0 < 0), ("right", x1 > w), ("top", y0 < 0), ("bottom", y1 > h)) if hit]


def _cut(tr: Track, id_: str, solid, f: int) -> dict | None:
    cam = tr.cams[f]
    pts = [cam.project(c) for c in solid[0]]
    if not all(pts):
        return None                              # part of it is behind the camera: not judged here
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    area = max((x1 - x0) * (y1 - y0), 1e-9)
    if area > BIG_AREA * cam.w * cam.h or any(_span(solid[0], k)[1] - _span(solid[0], k)[0] > BIG_M for k in (0, 2)):
        return None
    inside = max(0.0, min(x1, cam.w) - max(x0, 0)) * max(0.0, min(y1, cam.h) - max(y0, 0)) / area
    if not MOST <= inside <= 1 - MIN_CUT:
        return None
    return {"item": id_, "outside": round(1 - inside, 3), "edges": _edges(x0, y0, x1, y1, cam.w, cam.h)}


def _ground_top(tr: Track, shapes: dict, f: int) -> float:
    tops = [_span(s[0], 1)[1] for i, s in shapes.items() if _is_ground(tr, i, f) and _span(s[0], 1)[1] - _span(s[0], 1)[0] < GAP_M]
    return max(tops) if tops else 0.0


def _is_ground(tr: Track, id_: str, f: int) -> bool:
    return id_ == "ground" or bool(tr.fr.values(id_, f).get("backdrop"))


def _supported(me: str, shapes: dict, low: float, box) -> bool:
    """Something else touches or holds the lowest point: its box overlaps this one's footprint and its height range reaches low."""
    for j, s in shapes.items():
        if j == me:
            continue
        (a0, a1), (b0, b1), (c0, c1) = (_span(s[0], k) for k in (0, 2, 1))
        if a0 < box[1] and box[0] < a1 and b0 < box[3] and box[2] < b1 and c0 - GAP_M <= low <= c1 + GAP_M:
            return True
    return False


def _frame_faults(data: dict, info: dict, f: int, folder) -> dict:
    """{'cut': [...], 'floating': {id: gap}, 'sinking': {id: depth}} at frame f."""
    tr = Track(data, info, range(f, f + 1), folder)
    shapes = {}
    for id_ in tr.ids():
        if tr.shown(id_, f):
            row = tr.row(id_, f)
            if row["solid"]:
                shapes[id_] = row["solid"]
    ground = _ground_top(tr, shapes, f)
    out = {"cut": [], "floating": {}, "sinking": {}}
    for id_, s in shapes.items():
        if _is_ground(tr, id_, f):
            continue
        if c := _cut(tr, id_, s, f):
            out["cut"].append(c)
        (x0, x1), (z0, z1), (low, _) = (_span(s[0], k) for k in (0, 2, 1))
        if low < ground - GAP_M:
            out["sinking"][id_] = ground - low
        elif low > ground + GAP_M and not _supported(id_, shapes, low, (x0, x1, z0, z1)):
            out["floating"][id_] = low - ground
    return out


def scene(data: dict, info: dict, frames: list[int], folder=None) -> list[dict]:
    """cut_edge (any sampled frame), floating and sinking (every sampled frame) from the scene's geometry through the shot camera."""
    per = []
    for f in frames:
        try:
            per.append((f, _frame_faults(data, info, f, folder)))
        except ValueError:                       # something's size isn't known here (an import): nothing judged
            continue
    out, seen = [], set()
    for f, r in per:
        for c in r["cut"]:
            if (id_ := f"cut_edge:{c['item']}") not in seen:
                seen.add(id_)
                out.append(F.fault(id_, f"{c['item']} is cut by the {' and '.join(c['edges'])} edge of the picture ({c['outside'] * 100:.0f} % of it is outside)",
                                   f"move the camera back or frame it whole (shot.frame on {c['item']}), or move {c['item']} inside; if the cut is meant, keep it", when_of(info, f)))
    for kind, word, fix in (("floating", "floats {m:.2f} m above the ground with nothing under it", "place_on the ground: y = {y:.3f}; if it is meant to hover, keep it"),
                            ("sinking", "sinks {m:.2f} m into the ground", "lift it: place_on the ground, y = {y:.3f}")):
        if not per:
            continue
        common = set.intersection(*(set(r[kind]) for _, r in per))
        for id_ in sorted(common):
            m = per[0][1][kind][id_]
            sign = 1 if kind == "sinking" else -1
            y = _own_y(data, id_) + sign * m
            out.append(F.fault(f"{kind}:{id_}", f"{id_} " + word.format(m=m), fix.format(y=y), when_of(info, per[0][0])))
    return out


def _own_y(data: dict, id_: str) -> float:
    """The item's own y (its stored value), for a concrete fix; 0 when it is keyed or inside a group."""
    stack = list(data.get("items", []))
    while stack:
        it = stack.pop()
        if it["id"] == id_:
            return float(it.get("y", 0.0) or 0.0)
        stack += it.get("children", [])
    return 0.0


def check(data: dict, info: dict, frames: list[int], pngs: dict, folder=None) -> list[dict]:
    """Every fault of the shot at `frames`: pictures (`pngs`: {frame: path}, a frame may be missing) and geometry. Ids are unique."""
    found = []
    for f, png in pngs.items():
        found += picture(png, info["id"], when_of(info, f))
    found += scene(data, info, frames, folder)
    unique = {}
    for x in found:
        unique.setdefault(x["id"], x)
    return list(unique.values())


def sample(info: dict, count: int = 3) -> list[int]:
    """Frames to judge a shot at: its first, middle and last (fewer for a short shot)."""
    a, b = info["start"], info["end"]
    return sorted({a, (a + b) // 2, b}) if count >= 3 else [a]


def deliver(found: list[dict], keep: dict | None, where: str, files: list) -> list[str]:
    """faults.deliver for several files: every file that is there is held back as <name>.NOT-DONE<ext> when a fault is open."""
    files = [Path(f) for f in files if f and Path(f).is_file()]
    try:
        return F.deliver(found, keep, where, files[0] if files else None)
    except RostrumError:
        for p in files[1:]:
            held = p.with_name(f"{p.stem}.NOT-DONE{p.suffix}")
            held.unlink(missing_ok=True)
            p.replace(held)
        raise
