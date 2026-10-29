"""A wave that reads on screen (3D gaps 7, Hello: judges saw "no wave"), entries of the shot's one fault list (faults.py),
for each joint keyed back and forth (pose_faults._swings), measured on the hand through the shot camera:

  wave_small:<clay>.<joint>    the typical swing (the hand's path between two turning points) sweeps less than SMALL of the
                               picture's height; names the px, the %, and how many degrees more / cm farther out.
  wave_in_step:<clay>.<joint>  the swing repeats on the whole or half second, so stills one second apart (0.5, 1.5 … s, or
                               0, 1, 2 … s: what judges and contact sheets see) catch the hand at the same place: their spread
                               is under IN_STEP of the swing's own sweep.

The hand is the swinging part's tip (the ball farthest from the joint at rest), sampled every EVERY frames over the swing's
keyed span. A swing whose whole motion already reads as still is pose_faults' reads_still: one fault per problem.
"""
from __future__ import annotations

import math
import statistics

from rostrum_core.mcp import faults as F

from . import aim, pose_body as PB, skin
from .motion_track import Camera

SMALL = 0.06             # a swing sweeping less than this share of the picture's height reads as a twitch
IN_STEP = 0.30           # stills a second apart spread less than this share of the swing's sweep: the same pose
TURN = 0.15              # a turning point: the hand comes back by this share of its whole range
EVERY = 2                # frames between samples


def wave_faults(track, info: dict, id_: str, item: dict, balls, posed, keyed) -> list[dict]:
    from .pose_faults import STILL, _chain, _moves, _swings
    out, bones = [], skin.bones_of(item)
    par, names = PB.parents(item), PB.joint_names(item)
    rest = skin.transforms(bones)
    scale = PB.scale_of(track.fr.world(id_, info["start"]))
    for joint in sorted(n for n in keyed if _swings(bones[n][0]) and _limb(names[n])):
        sub = [n for n in range(len(par)) if joint in _chain(par, n)]
        moved = _moves(track, posed, balls, sub)
        if moved is None or moved < STILL * info["width"]:
            continue                                                     # reads_still says it
        root = aim.point(rest[joint], [0.0, 0.0, 0.0])
        own = [i for i, (_, _, b) in enumerate(balls) if b in sub]
        tip = max(own, key=lambda i: math.dist(balls[i][0], root))
        span, deg = _span(bones[joint][0])
        w = _measure(track, info, id_, balls[tip], span)
        if w is None:
            continue
        name, h = names[joint], info["height"]
        when = f"{span[0]:.1f}–{span[1]:.1f} s"
        if w["sweep"] < SMALL * h:
            k = SMALL * h * 1.15 / max(w["sweep"], 0.5)
            lever = math.dist(balls[tip][0], root) * scale
            out.append(F.fault(
                f"wave_small:{id_}.{name}",
                f"{id_}'s {name} swings {w['swings']} times but each swing moves its end only {w['sweep']:.0f} px "
                f"({w['sweep'] / h * 100:.1f} % of the picture's height): on screen it reads as a twitch, not a wave",
                f"swing {name} about {deg * (k - 1):.0f}° more end to end (now {deg:.0f}°), or put its end about "
                f"{lever * (k - 1) * 100:.0f} cm farther from the joint (pose it farther out), so each swing sweeps at least "
                f"{SMALL * 100:.0f} % of the picture's height; if a small move is meant, keep it", when))
        if w["spread"] is not None and w["spread"] < IN_STEP * w["sweep"]:
            out.append(F.fault(
                f"wave_in_step:{id_}.{name}",
                f"{id_}'s {name} swings every {w['period']:.2f} s: stills one second apart (at {w['grid']}) catch its end "
                f"within {w['spread']:.0f} px of the same place ({w['sweep']:.0f} px swing), so every still shows the same pose",
                f"key the swing so it does not repeat on the whole or half second: turning points every 0.35 s (a 0.7 s "
                f"swing) or 0.65 s (1.3 s), e.g. c.bend(\"{name}\", {{t0 + 0.35 * i: …}}); if a still pose is meant, keep it",
                when))
    return out


def _span(bone: dict) -> tuple[tuple[float, float], float]:
    """((first, last) time of the swing's turning keys, seconds; the typical swing between them, degrees)."""
    best = ((0.0, 0.0), 0.0)
    for k in skin.TURN:
        ks = sorted((x for x in bone.get("keys", []) if x.get("prop") == k), key=lambda x: x["t"])
        turns = [b for a, b, c in zip(ks, ks[1:], ks[2:]) if (b["v"] - a["v"]) * (c["v"] - b["v"]) < 0]
        if len(turns) < 2:
            continue
        deg = statistics.median(abs(b["v"] - a["v"]) for a, b in zip(turns, turns[1:]))
        if deg > best[1]:
            best = ((turns[0]["t"], turns[-1]["t"]), deg)
    return best


def _measure(track, info: dict, id_: str, ball, span) -> dict | None:
    """The tip on screen over the span: its typical swing (px between turning points), swings, period, and the spread of
    stills one second apart (the worse of the half- and whole-second grids); None when unseen or not a swing."""
    fr, fps, s0 = track.fr, info["fps"], info["start"]
    lo, hi = max(s0, fr.frames[0]), min(info["end"], fr.frames[-1])
    at = lambda f: _screen(track, info, id_, ball, f)                       # noqa: E731
    pts = {f: p for f in range(lo, hi + 1, EVERY) if span[0] <= fr.held(id_, f) / fps <= span[1] and (p := at(f))}
    if len(pts) < 6:
        return None
    axis = _axis(list(pts.values()))
    s = {f: p[0] * axis[0] + p[1] * axis[1] for f, p in pts.items()}
    ext = _turning(s, TURN * (max(s.values()) - min(s.values())))
    if len(ext) < 3:
        return None
    sweep = statistics.median(abs(s[b] - s[a]) for a, b in zip(ext, ext[1:]))
    period = statistics.median(b - a for a, b in zip(ext, ext[2:])) / fps if len(ext) >= 3 else 0.0
    spread, grid = None, ""
    for off in (0.5, 0.0):
        fs = [round(s0 + (off + n) * fps) for n in range(int((hi - s0) / fps) + 1)]
        seen = [p for f in fs if ext[0] <= f <= ext[-1] and (p := at(f))]
        if len(seen) >= 3:
            d = max(math.dist(a, b) for a in seen for b in seen)
            if spread is None or d < spread:
                spread, grid = d, f"{off:g}, {off + 1:g}, {off + 2:g} … s"
    return {"sweep": sweep, "swings": len(ext) - 1, "period": period, "spread": spread, "grid": grid}


def _screen(track, info, id_, ball, f):
    if not track.fr.frames[0] <= f <= track.fr.frames[-1]:
        return None
    cam = track.cams.get(f) or Camera(track.fr, info["camera"], f, info["width"], info["height"])
    return cam.project(PB.posed(track.fr, id_, [ball], f)[0][0])


def _axis(pts: list) -> tuple[float, float]:
    """The direction the points spread most along (their main axis)."""
    mx, my = sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)
    a = sum((x - mx) ** 2 for x, _ in pts)
    b = sum((x - mx) * (y - my) for x, y in pts)
    c = sum((y - my) ** 2 for _, y in pts)
    t = 0.5 * math.atan2(2 * b, a - c)
    return math.cos(t), math.sin(t)


def _turning(s: dict, back: float) -> list[int]:
    """Frames where the value turns round (it then comes back by more than `back`), the span's two ends included."""
    fs = sorted(s)
    out, hi, lo, way = [fs[0]], fs[0], fs[0], 0
    for f in fs[1:]:
        hi, lo = (f if s[f] > s[hi] else hi), (f if s[f] < s[lo] else lo)
        if way >= 0 and s[hi] - s[f] > back:
            out += [hi] if hi != out[-1] else []
            way, lo = -1, f
        elif way <= 0 and s[f] - s[lo] > back:
            out += [lo] if lo != out[-1] else []
            way, hi = 1, f
    end = hi if way > 0 else lo if way < 0 else fs[-1]
    return out + ([end] if end != out[-1] else [])


def _limb(name: str) -> bool:
    """A left or right part (an arm, a hand, a leg) waves; a head tilt or a body sway is secondary motion, not a wave."""
    return name.endswith((".L", ".R")) or name.startswith(("Left", "Right"))
