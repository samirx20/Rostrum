"""Where a shot's fall is on screen (round 2 of the 3D gaps: "nobody sees the fall"): per falling thing and cloth in the
stored result, the frames it moves, how many of them the shot camera's picture shows it in, and where it is when it is
not (above, below or beside the picture). Plain-words lines with the fix, for look_motion, the render reply (`fall_note`)
and the window.

    rows = views(doc.data, info, folder)                 # [{item, kind, moving, onScreen, offScreen, enters, lands, …}]
    text = fall_note(doc.data, "drop", folder)           # "" when every fall is seen; else one line per thing

"Moving" here is moving enough to see: a step of at least MOVE_M a frame by the thing's fastest point (a cloth: by its
points on average), so a cloth's last settling and a ball's tiny roll at rest don't count. A thing is "on screen" at a
frame when any of its box (a cloth: the box round its points) is in the picture. A copies item is judged copy by copy
(copies_fall.py: a staggered stream is many short falls, not one).
Measured from the stored result as the viewport plays it (Timing and Simplify applied, like look_motion).
"""
from __future__ import annotations

from rostrum_core.cache import CACHE

from .. import aim
from ..motion_track import Camera
from ..resolve import Frames
from . import fields as SF
from .cloth_check import frames_of
from .copies_fall import judge
from .inputs import KIND, bodies, shot_value, value
from .result import read, stylized
from .state import state

MOVE_M = 0.002        # m a frame: slower than this is settling, not falling (5 cm/s at 24 fps)
MIN_ON = 4            # a drop seen on fewer frames than this is named: it reads as a pop, not a fall
_FIX_UP = ("start it inside the picture, near its top: the sim.start_in_view operation (fromTop 0.1), or the "
           "Simulation group's Start in view button")
_FIX_LATER = "and give the shot a moment before it drops: fallStart (Falls from)"


def _corners(lo, hi) -> list[list[float]]:
    return [[(lo, hi)[i][0], (lo, hi)[j][1], (lo, hi)[k][2]] for i in (0, 1) for j in (0, 1) for k in (0, 1)]


def _box(points) -> list[list[float]]:
    return _corners([min(p[k] for p in points) for k in range(3)], [max(p[k] for p in points) for k in range(3)])


def _step(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _paths(data: dict, info: dict, folder, where, fr: Frames) -> dict[str, dict]:
    """Per moving thing {"kind", "frames": [points per shot frame], "pace": [step per frame (m)]}."""
    from ..item_bounds import world_box
    res, shot = read(where), _shot(data, info["id"])
    step, simplify = SF.TIMINGS[shot_value(shot, "simTiming")], int(shot_value(shot, "simSimplify"))
    s0, s1 = info["start"], info["end"]
    span = range(s0, s1 + 1)
    out = {}
    for item in bodies(data):
        kind, id_ = value(item, "simulate"), item["id"]
        if kind == "falls" and (rows := res.rows_of(id_)):
            per_row = [[p for p, _ in stylized(res, r, span, s0, step, simplify)] for r in rows]
            if item["type"] == "copies":                         # a copy's row is in its copies item's own space
                out[id_] = {"kind": "copies", "tracks": [[aim.point(fr.world(id_, f), p) for f, p in zip(span, ps)]
                                                         for ps in per_row]}
                continue
            else:
                try:
                    lo, hi = world_box(data, [id_], s0 / info["fps"])
                except ValueError:
                    continue
                pivot = per_row[0][0]
                offs = [[c[k] - pivot[k] for k in range(3)] for c in _corners(lo, hi)]
                pts = [[[p[k] + o[k] for k in range(3)] for o in offs] for p in per_row[0]]
            pace = [max(_step(a, b) for a, b in zip(pts[i - 1], pts[i])) for i in range(1, len(pts))]
            out[id_] = {"kind": "falls", "frames": pts, "pace": pace,
                        "low": [min(q[1] for q in ps) for ps in pts]}
        elif kind == "cloth":
            try:
                n, nf, raw = frames_of(where, id_)
            except OSError:
                continue
            place = fr.world(id_, s0)
            boxes, mids = [], []
            for f in span:
                i = min(max(f - s0, 0), nf - 1)
                if step > 1:
                    i = min(((f - s0) // step) * step, nf - 1)
                o = i * n * 3
                world = [aim.point(place, raw[o + 3 * j:o + 3 * j + 3]) for j in range(0, n, max(1, n // 400))]
                boxes.append(_box(world))
                mids.append(world)
            pace = [sum(_step(a, b) for a, b in zip(mids[i - 1], mids[i])) / len(mids[i]) for i in range(1, len(mids))]
            out[id_] = {"kind": "cloth", "frames": boxes, "pace": pace, "low": [sum(q[1] for q in w) / len(w) for w in mids]}
    return out


def _shot(data: dict, shot_id: str) -> dict:
    from ..compile import _shot as shot
    return shot(data, shot_id)


def classify(frames: list[int], pace: list[float], seen: list[str], fps: float, low: list[float] | None = None) -> dict:
    """The facts of one thing from its per-frame step (len frames - 1, metres), where the picture has it at each frame
    ("in" | "part" | "out", or "above" | "below" | "side" when out) and its height per frame (`low`: its lowest point; a
    cloth: its points' mean). The drop is from its first move until it stops going down (its first landing); what it
    does after (bounces, rolls, settling folds) is the rest of the move. Pure arithmetic: the tests run it on made-up rows."""
    moving = [frames[i + 1] for i, d in enumerate(pace) if d >= MOVE_M]
    if not moving:
        return {"moving": None, "movingFrames": 0, "onScreen": 0, "offScreen": 0, "enters": None, "lands": None,
                "where": None, "startsAtRest": True, "drop": None, "underway": False}
    at = {f: s for f, s in zip(frames, seen)}
    shown = lambda f: at[f] in ("in", "part")  # noqa: E731
    first = max(frames.index(moving[0]) - 1, 0)       # it leaves where it was one frame earlier
    end = first
    low = low or [0.0] * len(frames)
    while end + 1 < len(frames) and low[end] - low[end + 1] >= MOVE_M / 2:
        end += 1
    drop = frames[first:end + 1] if end > first else [moving[0]]
    # already moving at speed on the first step (a fall from rest starts slowly and speeds up): the shot opens mid-fall
    underway = first == 0 and len(pace) > 1 and pace[0] >= 0.7 * max(pace[1:4])
    on = [f for f in drop if shown(f)]
    off = [f for f in drop if not shown(f)]
    sides = [at[f] for f in off]
    return {"moving": [moving[0], moving[-1]], "movingFrames": len(moving), "drop": [drop[0], drop[-1]],
            "onScreen": len(on), "offScreen": len(off), "enters": on[0] if on else None, "lands": drop[-1],
            "where": max(set(sides), key=sides.count) if sides else None, "startsAtRest": False,
            "underway": underway, "seconds": round(len(on) / fps, 2), "drop_m": round(low[first] - low[end], 3)}


def line(id_: str, kind: str, facts: dict, fps: float) -> tuple[str, bool]:
    """(the plain-words line, whether it needs a fix)."""
    what = {"cloth": "cloth", "copies": "copies", "falls": "fall"}[kind]
    if facts["startsAtRest"]:
        return (f"{id_} ({what}) never visibly moves: it starts already at rest (on what it should land on, or with "
                f"nothing to fall to). To see it fall: {_FIX_UP} {_FIX_LATER}."), True
    a, b = facts["drop"]
    on, off, n = facts["onScreen"], facts["offScreen"], b - a + 1
    head = (f"{id_} ({what}) drops {facts['drop_m']:g} m in frames {a}–{b} ({n} frames, until it first lands; it moves "
            f"until frame {facts['moving'][1]}): {on} of them on screen, {off} outside the picture")
    if on == 0:
        return f"{head}. The whole fall happens {_where(facts['where'])}: nobody sees it. {_FIX_UP[0].upper() + _FIX_UP[1:]}.", True
    if facts["where"] == "above" and off > 0 and on < 2 * off:
        return (f"{head}. Most of the fall happens above the picture: it enters at frame {facts['enters']} and lands at "
                f"frame {b} ({on} frame{'' if on == 1 else 's'} on screen). {_FIX_UP[0].upper() + _FIX_UP[1:]}."), True
    if on < MIN_ON:
        return (f"{head}. It is seen dropping for only {on} frame{'' if on == 1 else 's'} (from frame {facts['enters']}): a pop, not a fall. "
                f"To see more of it: {_FIX_UP}, {_FIX_LATER}; a lighter cloth (clothWeight) falls slower."), True
    if off > on:
        return (f"{head}. Most of the drop happens {_where(facts['where'])}; it is seen dropping for {on / fps:.2f} s. "
                f"{_FIX_UP[0].upper() + _FIX_UP[1:]}."), True
    return f"{head}; seen dropping for {on / fps:.2f} s.", False


def _where(w) -> str:
    return {"above": "above the picture", "below": "below the picture", "side": "beside the picture"}.get(w, "outside the picture")


def _seen(cam: Camera, corners) -> str:
    how = cam.holds(corners)
    if how != "out":
        return how
    pts = [p for p in (cam.project(c) for c in corners) if p]
    if not pts:
        return "side"
    if all(y < 0 for _, y in pts):
        return "above"
    if all(y > cam.h for _, y in pts):
        return "below"
    return "side"


def views(data: dict, info: dict, folder=None) -> list[dict]:
    """Per falling thing and cloth of the shot's stored result (or its older one): {"item", "kind", "line", "fix", and
    the facts of `classify`}. [] when nothing is simulated or nothing is stored."""
    st = state(data, info["id"], folder)
    key = {"stored": st.get("key"), "out of date": st.get("storedKey")}.get(st["state"])
    where = CACHE.get(KIND, key) if key else None
    if where is None:
        return []
    s0, s1 = info["start"], info["end"]
    fr = Frames(data, range(s0, s1 + 1), info["fps"], folder)
    cams = {f: Camera(fr, info["camera"], f, info["width"], info["height"]) for f in range(s0, s1 + 1)}
    out = []
    breezes = {b["id"]: float(value(b, "clothWind")) for b in bodies(data) if value(b, "simulate") == "cloth"}
    for id_, p in _paths(data, info, folder, where, fr).items():
        if p["kind"] == "copies":
            facts, text, fix = judge(id_, p["tracks"], list(range(s0, s1 + 1)), lambda f, q: _seen(cams[f], [q]), info["fps"])
            out.append({"item": id_, "kind": "copies", **facts, "line": text, "fix": fix})
            continue
        seen = [_seen(cams[f], c) for f, c in zip(range(s0, s1 + 1), p["frames"])]
        facts = classify(list(range(s0, s1 + 1)), p["pace"], seen, info["fps"], p["low"])
        text, fix = line(id_, p["kind"], facts, info["fps"])
        out.append({"item": id_, "kind": p["kind"], **facts, "line": text, "fix": fix, "breeze": breezes.get(id_, 0.0)})
    return out


def fall_note(data: dict, shot_id: str, folder=None, frames: tuple[int, int] | None = None) -> str:
    """For a render, export or look reply: one line per falling thing or cloth whose fall the shot camera does not show
    well (all of it outside the picture, most of it above, under MIN_ON on screen, or already at rest), and what the
    cut `frames` (first, last; default the whole shot) shows of it (cut_note: it opens mid-drop or after the landing,
    the shot opens with a thing already falling, a still stretch at the end). "" when every fall is seen, or nothing
    is simulated / stored."""
    from ..compile import shot_info
    from .cut_note import cut_lines
    try:
        info = shot_info(data, shot_id)
        rows = views(data, info, folder)
    except (ValueError, OSError):
        return ""
    f0, f1 = frames or (info["start"], info["end"])
    return " ".join([r["line"] for r in rows if r["fix"]] + cut_lines(rows, f0, f1, info["start"], info["fps"]))
