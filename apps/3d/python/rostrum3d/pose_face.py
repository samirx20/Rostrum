"""face_unmatched:<a>~<b>, a pose fault (pose_faults.py): a pair of features on one part of a figure (two eyes: small
attached meshes of about one size, mirrored about the figure's middle) that don't match (gaps7 Hello: judges saw "two
eyes of different size and height, the brow shrinks one eye").

  At rest, in the part's own frame: their sizes differ by more than SIZE, or their heights by more than HEIGHT of their
  size. The fix gives the size or the height to match.
  On the picture: at a checked frame one eye's seen disc is under SEEN of the other's, measured by rays from the shot
  camera to points on each eye's front against the clay's posed balls. Said why: a lump of the clay (a brow, a nose)
  covers it (move that lump off the eye by about how much), or the part turned so the far eye sinks into it (turn the
  part about how many degrees less). A normal three-quarter turn stays silent; an eye on the part's outline is on_rim's.
"""
from __future__ import annotations

import math

from rostrum_core.mcp import faults as F

from . import aim, follow, pose_body as PB

SIZE = 0.15              # own sizes differing by more than this share: unmatched
HEIGHT = 0.25            # heights differing by more than this share of their size: unmatched
SEEN = 0.65              # one eye's seen radius under this share of the other's on the picture
GRID = 9                 # rays per eye across its disc: GRID × GRID


def face_faults(track, info, id_, item, balls, posed, features) -> list[dict]:
    """features: pose_faults' [(item id, own size, bone it sits on, where at the first frame)]."""
    out = []
    for (a, sa, on, ra), (b, sb, _, rb) in _pairs(track, id_, posed, features):
        when = "at rest"
        if abs(sa - sb) > SIZE * max(sa, sb):
            small, big = (a, b) if sa < sb else (b, a)
            out.append(F.fault(f"face_unmatched:{a}~{b}", f"{a} and {b} are a pair on {id_} but differ in size: radius "
                               f"{sa * 100:.2f} cm vs {sb * 100:.2f} cm", f"give {small} radius {max(sa, sb):.4f}, as {big}; "
                               "if the difference is meant, keep it", when))
            continue
        if abs(ra[1] - rb[1]) > HEIGHT * (sa + sb) / 2:
            low, high, dy = (a, b, rb[1] - ra[1]) if ra[1] < rb[1] else (b, a, ra[1] - rb[1])
            out.append(F.fault(f"face_unmatched:{a}~{b}", f"{a} sits {dy * 100:.1f} cm lower than {b} on {id_}: the pair "
                               "reads lopsided", f"raise {low} by {dy:.3f} (its y), level with {high}; if the tilt is meant, "
                               "keep it", when))
            continue
        seen = _seen(track, info, id_, item, balls, posed, a, sa, b, sb, on)
        if seen:
            out.append(seen)
    return out


def _pairs(track, id_, posed, features) -> list:
    """Mirrored features of about one size on one part, with their places in the clay's own space at rest."""
    fr, f0 = track.fr, next(iter(posed))
    rest = []
    for iid, own, on, here0 in features:
        back = aim.invert(aim.compose(fr.world(id_, f0), follow.bone_move(fr, id_, on, f0)))
        rest.append((iid, own, on, aim.point(back, here0)))
    out, used = [], set()
    for n, (a, sa, on, ra) in enumerate(rest):
        for b, sb, onb, rb in rest[n + 1:]:
            if a in used or b in used or on != onb or ra[0] * rb[0] >= 0 or min(sa, sb) < 0.5 * max(sa, sb):
                continue
            if abs(ra[0] + rb[0]) <= sa + sb and abs(ra[2] - rb[2]) <= sa + sb:
                out.append(((a, sa, on, ra), (b, sb, on, rb)))
                used |= {a, b}
    return out


def _seen(track, info, id_, item, balls, posed, a, sa, b, sb, on) -> dict | None:
    """The worst checked frame where one eye shows under SEEN of the other: a fault saying why, else None."""
    fr, pieces, worst = track.fr, PB.rest_pieces(item), None
    for f, now in posed.items():
        cam = track.cams.get(f)
        if cam is None:
            continue
        ca, cb = aim.point(fr.world(a, f), [0.0, 0.0, 0.0]), aim.point(fr.world(b, f), [0.0, 0.0, 0.0])
        (fa, cov_a), (fb, cov_b) = _visible(cam, ca, sa, now), _visible(cam, cb, sb, now)
        da, db = _depth(cam, ca), _depth(cam, cb)
        if da <= 0 or db <= 0:
            continue
        ea, eb = sa / da * math.sqrt(fa), sb / db * math.sqrt(fb)          # seen radius, in the picture's scale
        share = min(ea, eb) / max(ea, eb, 1e-9)
        if share < SEEN and (worst is None or share < worst[0]):
            small = (a, ca, sa, cov_a, cb) if ea < eb else (b, cb, sb, cov_b, ca)
            worst = (share, f, small)
    if worst is None:
        return None
    share, f, (eye, c, own, cover, other) = worst
    t = (f - info["start"]) / info["fps"]
    names, main = PB.joint_names(item), _main_ball(balls, on)
    lump = max(cover, key=cover.get) if cover else None
    what = f"{eye} shows {(1 - share) * 100:.0f} % smaller than its pair on the picture at {t:.1f} s"
    if lump is not None and lump != main and pieces[lump][0]:
        name = pieces[lump][0]
        fix = (f"the {name} lump covers it: move the {name} about {2 * own * (1 - share) * 100:.1f} cm off the eye "
               f"(up for a brow), or make it smaller; if it is meant (a squint), keep it")
        what += f" (the {name} lump covers it)"
    else:
        head = posed[f][main][0]
        toward = [e - h for e, h in zip(track.cams[f].eye, head)]
        deg = (_angle(c, head, toward) - _angle(other, head, toward)) / 2
        fix = (f"turn the {names[on]} about {max(deg, 5):.0f}° less at {t:.1f} s (c.bend(\"{names[on]}\", …)), or turn the "
               "camera toward the face; if the side view is meant, keep it")
        what += f" (the {names[on]} turned so it sinks)"
    return F.fault(f"face_unmatched:{a}~{b}", what, fix, f"frame {f}, {t:.2f} s")


def _main_ball(balls, on) -> int:
    """The biggest ball on the part's bone: the part itself (the head), not a lump added on it."""
    return max((n for n, (_, _, bone) in enumerate(balls) if bone == on), key=lambda n: balls[n][1], default=0)


def _depth(cam, c) -> float:
    return -sum((x - e) * k for x, e, k in zip(c, cam.eye, cam.back))


def _angle(p, centre, toward) -> float:
    v = [x - c for x, c in zip(p, centre)]
    n = math.hypot(*v) * math.hypot(*toward) or 1.0
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(v, toward)) / n))))


def _visible(cam, c, r, balls) -> tuple[float, dict]:
    """(the share of the eye's disc the camera sees, {ball index: rays it stops}): rays to points on the eye's front."""
    o = cam.eye
    to = [e - x for e, x in zip(o, c)]
    n = math.hypot(*to) or 1.0
    to = [x / n for x in to]
    hit, total, cover = 0, 0, {}
    for gi in range(GRID):
        for gj in range(GRID):
            u, v = (2 * gi / (GRID - 1) - 1) * r, (2 * gj / (GRID - 1) - 1) * r
            if u * u + v * v > r * r:
                continue
            total += 1
            w = math.sqrt(r * r - u * u - v * v)
            p = [x + u * a + v * b + w * t for x, a, b, t in zip(c, cam.right, cam.up, to)]
            k = _blocker(o, p, balls)
            if k is None:
                hit += 1
            else:
                cover[k] = cover.get(k, 0) + 1
    return hit / max(total, 1), cover


def _blocker(o, p, balls) -> int | None:
    """The first ball the ray from o to p meets before p, or None."""
    d = [b - a for a, b in zip(o, p)]
    length = math.hypot(*d) or 1e-9
    d = [x / length for x in d]
    for k, (q, r, _) in enumerate(balls):
        oq = [b - a for a, b in zip(o, q)]
        tc = sum(x * y for x, y in zip(oq, d))
        d2 = sum(x * x for x in oq) - tc * tc
        if d2 >= r * r:
            continue
        th = tc - math.sqrt(r * r - d2)
        if 0 < th < length - 1e-4:
            return k
    return None
