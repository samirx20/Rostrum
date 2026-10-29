"""Faults first, for a 3D shot (rostrum_core/mcp/faults.py): what the shot camera's picture and the scene's geometry say is wrong,
named before anything else in a look / render reply.

Three checks, each with a stable fault id so `keep: {id: why}` names it across re-runs:
  dark:<shot> / blown:<shot>  the picture (its pixels): mean brightness under DARK_MEAN of full, or CLIPPED_PCT % of the pixels
                              with a channel at white (facts.measure; the same numbers inspect_exposure gives).
  out_of_frame:<item>         a shown shape (not ground-sized) wholly outside the picture on every sampled frame.
  cut_edge:<item>             a shown shape whose projected box (through the shot camera) crosses the picture's edge while most
                              of it (>= MOST) is inside. Ground / background-sized things (backdrop, a side over BIG_M m, a box
                              over BIG_AREA times the picture) are framing, not a subject.
  floating:<item> / sinking:<item>
                              a shape whose lowest point is more than GAP_M above the ground with nothing touching it from
                              below, or more than GAP_M below the ground (the ground: the backdrop's top, else y = 0). Judged on
                              the sampled frames together: a jump or a fall is not floating, so only a gap present on every one counts.
                              A thing the simulation moves (Falls, Cloth) is judged only where the stored result has it settled
                              (still from that frame to the shot's end): a sheet or a ball waiting for its Falls-from frame, or still
                              falling, has not landed yet (Drape, 3E round: "sheet floats 0.49 m above box" on a cloth's first
                              frame). A cloth's folds, and a fall not computed yet, aren't measured here: run_simulation's reply
                              says what each cloth ends on.
  flat_light:<item>           the biggest subject's lit and dark sides under light_faults.FLAT_STOPS apart in the picture
                              (light_faults.py; first picture only, not Stylized).
  separated:<part> / leaves_frame:<item> / no_floor:<shot> / through_body / touches_body / face_unmatched / off_body / on_rim / reads_still, and cut_edge:<cloth|copies> from the stored simulation: from the
                              document over the whole shot (rostrum3d/faults.py), in the same list.
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core.mcp import faults as F

from rostrum3d.faults import doc_faults
from rostrum3d.motion_track import Track
from rostrum3d.sim.inputs import MOVING, bodies, value

from . import light_faults, motion_sim

from .facts import measure
from .shot import seconds

DARK_MEAN = 0.08          # mean display brightness (0 black – 1 white) under this: the frame is nearly black
CLIPPED_PCT = 40.0        # share of pixels with any channel at white above this: blown out
GAP_M = 0.01              # 1 cm: lowest point this far above / below the ground
MOST = 0.5                # a cut subject has at least this share of its projected box inside the picture
MIN_CUT = 0.02            # ... and at least this share outside (a pixel's worth is not a cut)
BIG_M = 8.0               # a side longer than this is a floor or a wall
BIG_AREA = 2.0            # a projected box this many pictures large is a background
SETTLED_M = 0.002         # a simulated thing moving less than this (m) …
SETTLED_DEG = 0.5         # … and turning less than this from a frame to the shot's end has landed


def when_of(info: dict, frame: int) -> str:
    return f"frame {frame}, {seconds(info, frame):.2f} s"


def picture(png, shot: str, when: str) -> list[dict]:
    """dark / blown from a picture's pixels."""
    m = measure(Path(png))
    mean = m["luminance"]["mean"] / 255
    out = []
    if mean < DARK_MEAN:
        out.append(F.fault(f"dark:{shot}", f"the picture is nearly black: mean brightness {mean:.2f} of 1 (under {DARK_MEAN:g})",
                           "raise the key light about 2 stops (its intensity ×4) or put back the starting lights (key_light, rim_light, sky); look_frame what \"exposure\" shows the numbers", when))
    if m["clipped_pct"] > CLIPPED_PCT:
        out.append(F.fault(f"blown:{shot}", f"{m['clipped_pct']:g} % of the picture is blown out to white (over {CLIPPED_PCT:g} %)",
                           "lower the lights' intensity (halve it) or the shot's Exposure; look_frame what \"exposure\" shows where", when))
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
    if inside <= 0:                              # wholly outside: made but never seen
        return {"item": id_, "outside": 1.0, "edges": _edges(x0, y0, x1, y1, cam.w, cam.h)}
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


def _below(me: str, shapes: dict, low: float, box) -> tuple[str, float] | None:
    """The highest other shape under the footprint whose top is below `low`: (id, top), else None (the ground is under it)."""
    best = None
    for j, s in shapes.items():
        (a0, a1), (b0, b1), (_, top) = (_span(s[0], k) for k in (0, 2, 1))
        if j != me and a0 < box[1] and box[0] < a1 and b0 < box[3] and box[2] < b1 and top < low and (best is None or top > best[1]):
            best = (j, top)
    return best


def _simulated(data: dict, info: dict, folder) -> tuple[dict | None, set[str]]:
    """(motion_sim.moves for the shot, or None; the ids the simulation moves: Falls and Cloth)."""
    moving = {b["id"] for b in bodies(data) if value(b, "simulate") in MOVING}
    if not moving:
        return None, moving
    try:
        return motion_sim.moves(data, info, folder), moving
    except Exception:  # noqa: BLE001  no stored result readable: the moving things are just not judged
        return None, moving


def settled(per: dict | None, i: int) -> bool:
    """Whether a simulated thing's stored path (`per`: {prop: [value per shot frame]}) stays put from index i to the end."""
    if not per:
        return False                              # not computed, or a cloth / copies: where it lands is not known here
    for k, vals in per.items():
        if not vals:
            return False
        v0 = vals[min(i, len(vals) - 1)]
        if any(abs(v - v0) > (SETTLED_DEG if k.startswith("r") else SETTLED_M) for v in vals[min(i, len(vals) - 1):]):
            return False
    return True


def _frame_faults(data: dict, info: dict, f: int, folder, sim: dict | None = None, moving: set[str] = frozenset()) -> dict:
    """{'cut': [...], 'floating': {id: gap}, 'sinking': {id: depth}, 'judged': {ids}} at frame f; a simulated thing is
    judged for floating / sinking only where it has settled."""
    tr = Track(data, info, range(f, f + 1), folder, sim)
    shapes = {}
    for id_ in tr.ids():
        if tr.shown(id_, f):
            row = tr.row(id_, f)
            if row["solid"]:
                shapes[id_] = row["solid"]
    ground = _ground_top(tr, shapes, f)
    out = {"cut": [], "floating": {}, "sinking": {}, "judged": set()}
    moves = (sim or {}).get("moves", {})
    for id_, s in shapes.items():
        if _is_ground(tr, id_, f):
            continue
        if c := _cut(tr, id_, s, f):
            out["cut"].append(c)
        if id_ in moving and not settled(moves.get(id_), f - info["start"]):
            continue                              # still waiting to fall or falling: it hasn't landed yet
        out["judged"].add(id_)
        (x0, x1), (z0, z1), (low, _) = (_span(s[0], k) for k in (0, 2, 1))
        if low < ground - GAP_M:
            out["sinking"][id_] = ground - low
        elif low > ground + GAP_M and not _supported(id_, shapes, low, (x0, x1, z0, z1)):
            under = _below(id_, shapes, low, (x0, x1, z0, z1))
            out["floating"][id_] = (low - under[1], under[0]) if under else (low - ground, None)
    return out


def scene(data: dict, info: dict, frames: list[int], folder=None) -> list[dict]:
    """cut_edge (any sampled frame), floating and sinking (every sampled frame) from the scene's geometry through the shot camera."""
    if not _item(data, info.get("camera")):      # no camera item to look through: the engine names that itself, nothing to judge
        return []
    sim, moving = _simulated(data, info, folder)
    per = []
    for f in frames:
        try:
            per.append((f, _frame_faults(data, info, f, folder, sim, moving)))
        except ValueError:                       # something's size isn't known here (an import): nothing judged
            continue
    out, seen = [], set()
    never = set.intersection(*({c["item"] for c in r["cut"] if c["outside"] >= 1.0} for _, r in per)) if per else set()
    for f, r in per:
        for c in r["cut"]:
            gone = c["outside"] >= 1.0
            if gone and c["item"] not in never:      # outside only for a while (it moves in or out): not a fault
                continue
            if (id_ := f"{'out_of_frame' if gone else 'cut_edge'}:{c['item']}") not in seen:
                seen.add(id_)
                out.append(F.fault(id_, f"{c['item']} is wholly outside the picture (past the {' and '.join(c['edges'])} edge)",
                                   f"move it into the shot or frame it (shot.frame on {c['item']}); if it is meant to be unseen, keep it", when_of(info, f))
                           if gone else F.fault(id_, f"{c['item']} is cut by the {' and '.join(c['edges'])} edge of the picture ({c['outside'] * 100:.0f} % of it is outside)",
                                   f"move the camera back or frame it whole (shot.frame on {c['item']}), or move {c['item']} inside; if the cut is meant, keep it", when_of(info, f)))
    for kind, word, fix in (("floating", "floats {m:.2f} m above the ground with nothing under it", "place_on the ground: y = {y:.3f}; if it is meant to hover, keep it"),
                            ("sinking", "sinks {m:.2f} m into the ground", "lift it: place_on the ground, y = {y:.3f}")):
        if not per:
            continue
        judged = set().union(*(r["judged"] for _, r in per))
        common = {i for i in judged if all(i in r[kind] for _, r in per if i in r["judged"] or i not in moving)}
        for id_ in sorted(common):
            f0, r0 = next((f, r) for f, r in per if id_ in r[kind])
            m, on = r0[kind][id_] if kind == "floating" else (r0[kind][id_], None)
            sign = 1 if kind == "sinking" else -1
            y = _own_y(data, id_) + sign * m
            what, how = (word, fix) if on is None else (f"floats {{m:.2f}} m above {on} with nothing touching it",
                                                       f"{id_}.place_on({on}) (y = {{y:.3f}}); if it is meant to hover, keep it")
            out.append(F.fault(f"{kind}:{id_}", f"{id_} " + what.format(m=m), how.format(y=y), when_of(info, f0)))
    return out


def _item(data: dict, id_) -> dict | None:
    """The document's item `id_` (searched through groups), else None."""
    stack = list(data.get("items", []))
    while stack:
        it = stack.pop()
        if it.get("id") == id_:
            return it
        stack += it.get("children", [])
    return None


def _own_y(data: dict, id_: str) -> float:
    """The item's own y (its stored value), for a concrete fix; 0 when it is keyed or inside a group."""
    it = _item(data, id_)
    return float(it.get("y", 0.0) or 0.0) if it else 0.0


def check(data: dict, info: dict, frames: list[int], pngs: dict, folder=None, renderer: str | None = None) -> list[dict]:
    """Every fault of the shot at `frames`: pictures (`pngs`: {frame: path}, a frame may be missing) and geometry. Ids are unique.
    flat_light is judged on the first picture only (light_faults.py), never on a Stylized one."""
    found = []
    for f, png in pngs.items():
        found += picture(png, info["id"], when_of(info, f))
    if pngs and renderer != "stylized":
        f, png = next(iter(sorted(pngs.items())))
        found += light_faults.flat(data, info, f, png, folder, when_of(info, f))
    found += scene(data, info, frames, folder)
    unique = {}
    for x in found:
        unique.setdefault(x["id"], x)
    for x in doc_faults(data, info, folder, at=frames[0] if len(frames) == 1 else None):
        unique[x["id"]] = x                      # a cloth's / copies' own points beat their box (same id), the rest are new
        if x["id"].startswith("leaves_frame:"):     # one fault per thing: leaving the picture says more than being cut on the way
            unique.pop("cut_edge:" + x["id"].split(":", 1)[1], None)
    return list(unique.values())


def sample(info: dict, count: int = 3) -> list[int]:
    """Frames to judge a shot at: its first, middle and last (fewer for a short shot)."""
    a, b = info["start"], info["end"]
    return sorted({a, (a + b) // 2, b}) if count >= 3 else [a]


def deliver(found: list[dict], keep: dict | None, where: str, files: list) -> list[str]:
    """The checks on a final file are notes, never a refusal (Sam, 2026-10-29: "what if it's deliberate? we only provide
    tools"): the files stay under their names, `keep` marks the faults left on purpose, and the reply's NOT DONE line
    lists the rest. Returns apply_keep's notes plus one saying which faults the delivered file still shows."""
    notes = F.apply_keep(found, keep)
    left = F.still_open(found)
    if left:
        notes.append(f"{where}: written with {len(left)} open fault(s) as notes ({', '.join(f['id'] for f in left)}); "
                     "look at the file and decide")
    return notes
