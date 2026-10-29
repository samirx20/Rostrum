"""on_rim:<item>, a pose fault (pose_faults.py): a small feature on a figure (an eye, a nose) that the shot camera sees on or
past the outline of the part it sits on, so it reads as beside the part, not on it (gaps6 Hello r1 still 1: the head
turned ~40°, the eye on its rim stuck out past the head). Seen through the camera: the part's ball and the feature's ball
as discs on the picture; the feature's centre farther than RIM × the part's disc radius from its centre, or its disc
poking past the outline by more than POKE of its own width. The fix says how far to move the feature round the part
toward the camera (in its own x y z, staying on the part's surface), how many degrees less to turn the part at that time, or to turn the camera.
"""
from __future__ import annotations

import math

from rostrum_core.mcp import faults as F

from . import aim, follow, pose_body as PB, skin

RIM = 0.8                # the feature's centre this share of the part's seen radius from its middle: on the rim
POKE = 1 / 3             # … or this share of the feature's own width past the part's outline
AIM = 0.55               # the fix brings the feature's centre to this share of the part's radius


def _disc(cam, c, r):
    """(x px, y px, radius px) of a ball as the camera sees it; None behind the camera."""
    p = cam.project(c)
    depth = -sum((a - b) * k for a, b, k in zip(c, cam.eye, cam.back))
    return None if p is None or depth <= 0 else (p[0], p[1], r * cam.w / (2 * cam.tan_w * depth))


def on_rim(track, info, id_, item, balls, posed, features) -> list[dict]:
    """features: [(item id, its own size m, the bone it sits on)] (pose_faults' features on the figure)."""
    fr, names, out = track.fr, PB.joint_names(item), []
    for it, own, on in features:
        for f, now in posed.items():
            cam = track.cams.get(f)
            here = aim.point(fr.world(it, f), [0.0, 0.0, 0.0])
            part = [(c, r) for c, r, b in now if b == on]
            if cam is None or not part:
                continue
            c, r = min(part, key=lambda x: math.dist(x[0], here) - x[1])
            pd, ed = _disc(cam, c, r), _disc(cam, here, own)
            if pd is None or ed is None:
                continue
            d = math.hypot(ed[0] - pd[0], ed[1] - pd[1])
            poke = (d + ed[2] - pd[2]) / (2 * ed[2])
            if d <= RIM * pd[2] and poke <= POKE:
                continue
            out.append(F.fault(f"on_rim:{it}", f"{it} sits on the edge of {id_}'s {names[on]} as the camera sees it at "
                               f"{(f - info['start']) / info['fps']:.1f} s (it pokes {max(poke, 0) * 100:.0f} % past the outline): "
                               f"reads as beside the {names[on]}", _fix(track, info, id_, item, on, f, c, r, here, d / pd[2]),
                               f"frame {f}, {(f - info['start']) / info['fps']:.2f} s"))
            break
    return out


def _fix(track, info, id_, item, on, f, c, r, here, share) -> str:
    fr, names, cam = track.fr, PB.joint_names(item), track.cams[f]
    side = [h - k for h, k in zip(here, c)]
    along = sum(a * b for a, b in zip(side, cam.back))
    flat = [s - along * b for s, b in zip(side, cam.back)]          # the offset as the camera sees it, in the world
    n, size = math.hypot(*flat) or 1.0, math.hypot(*side)
    face = [size * (AIM * x / n + math.sqrt(1 - AIM * AIM) * b) for x, b in zip(flat, cam.back)]   # round the part, toward the camera
    move = [a - s for a, s in zip(face, side)]
    lin = aim.compose(fr.world(id_, f), follow.bone_move(fr, id_, on, f))[0]   # back into the figure's own space at rest
    inv = aim.invert((lin, [0.0, 0.0, 0.0]))
    dx, dy, dz = aim.point(inv, move)
    nudge = ", ".join(f"{k} {v:+.3f}" for k, v in zip("xyz", (dx, dy, dz)) if abs(v) >= 0.001)
    deg = math.degrees(math.asin(min(share, 1.0)) - math.asin(AIM))
    t = (f - info["start"]) / info["fps"]
    joint = next((b for b, _ in skin.bones_of(item) if b.get("joint") == names[on]), None)
    keyed = sorted({k["t"] for k in (joint or {}).get("keys", [])})
    at = min(keyed, key=lambda k: abs(k - t)) if keyed else None
    turn = (f"turn the {names[on]} about {deg:.0f}° less toward that side at {t:.1f} s (c.bend(\"{names[on]}\", …) key at "
            f"{at:g} s)" if at is not None else f"turn the {names[on]} about {deg:.0f}° toward the camera")
    return (f"{turn}; or move it round the {names[on]} toward the camera ({nudge or 'a little'} on its own position); "
            "or turn the camera toward the face; if the side view is meant, keep it")
