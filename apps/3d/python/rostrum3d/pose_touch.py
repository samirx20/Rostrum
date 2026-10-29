"""through_body / touches_body, pose faults (pose_faults.py): a part of a posed figure that passes into, or comes up against, a
part that is not its neighbour (gaps6 Hello: the waving hand through the head; gaps7 Hello: the raised arm grazing the
head's side, so arm and head read as one lump).

  through_body:<clay>.<joint>  the part is deeper into the other than at rest by more than THROUGH_M and THROUGH_R of the
                               thinner part's radius (TRUNK_R for a limb against the trunk it hangs from: a hanging arm
                               resting on the belly is fine).
  touches_body:<clay>.<joint>  not into it, but within the clearance (the larger blend, at least TOUCH_R of the thinner
                               radius) while at rest it was clear, and the two touch on the picture through the shot camera.
                               Not for a limb against its own trunk.

One note per keyed joint, the worst frame; a part into another outranks one touching it. The joint named is the keyed
one that moves the two apart (a limb's, never the trunk both hang from), with the degrees of turn that would clear the
part by CLEAR_M (or the clearance): a measurement, not an instruction.
"""
from __future__ import annotations

import math

from rostrum_core.mcp import faults as F

from . import aim, pose_body as PB, skin
from .pose_rim import _disc

THROUGH_M = 0.004        # a part this much deeper into another than at rest …
THROUGH_R = 0.35         # … and this share of the thinner part's radius passes through it
TRUNK_R = 0.5            # … this share for a limb against the trunk it hangs from
TOUCH_R = 0.3            # clearance: at least this share of the thinner part's radius (or the larger blend)
CLEAR_M = 0.01           # the fix turns the joint so the part clears by this


def chain(par: list[int], n: int) -> list[int]:
    out = []
    while n >= 0:
        out.append(n)
        n = par[n]
    return out


def mover(par, keyed, a: int, b: int) -> tuple[int | None, int | None]:
    """(the keyed joint that moves bone a's part relative to bone b's, the one for b's): the nearest keyed joint up each
    chain that the other chain doesn't share (the trunk both hang from moves them together)."""
    ca, cb = chain(par, a), chain(par, b)
    own = lambda c, other: next((n for n in c if n in keyed and n not in other), None)       # noqa: E731
    return own(ca, set(cb)), own(cb, set(ca))


def through_touch(track, info, id_, item, balls, posed, keyed) -> list[dict]:
    par, names, pieces = PB.parents(item), PB.joint_names(item), PB.rest_pieces(item)
    near = lambda a, b: a == b or par[a] == b or par[b] == a                       # noqa: E731
    pairs = []
    for i, (p, ri, a) in enumerate(balls):
        for j, (q, rj, b) in enumerate(balls):
            if i < j and not near(a, b) and mover(par, keyed, a, b) != (None, None):
                trunk = a in chain(par, b) or b in chain(par, a)
                pairs.append((i, j, ri + rj - math.dist(p, q), max(pieces[i][1], pieces[j][1]), trunk))
    worst: dict[int, tuple] = {}
    for f, now in posed.items():
        cam = track.cams.get(f)
        for i, j, d0, blend, trunk in pairs:
            (p, ri, a), (q, rj, b) = now[i], now[j]
            thin = min(ri, rj)
            over = ri + rj - math.dist(p, q) - max(d0, 0.0)
            clear = max(blend, TOUCH_R * thin)
            if over > max(THROUGH_M, (TRUNK_R if trunk else THROUGH_R) * thin):
                rank, kind, need = (1, over), "through", over + CLEAR_M
            elif not trunk and -d0 > clear and (gap := math.dist(p, q) - ri - rj) < clear and _seen_touching(cam, now[i], now[j]):
                rank, kind, need = (0, clear - gap), "touch", clear - gap
            else:
                continue
            ja, jb = mover(par, keyed, a, b)
            mi, mj = math.dist(p, balls[i][0]), math.dist(q, balls[j][0])
            m, o, joint = (i, j, ja) if jb is None or (ja is not None and mi >= mj) else (j, i, jb)
            if joint not in worst or rank > worst[joint][0]:
                worst[joint] = (rank, kind, need, f, m, o, clear)
    return [_fault(track, info, id_, item, names, posed, joint, *w[1:]) for joint, w in worst.items()]


def _seen_touching(cam, x, y) -> bool:
    """The two balls' discs meet on the picture (a gap only the depth shows is not seen)."""
    if cam is None:
        return False
    dx, dy = _disc(cam, x[0], x[1]), _disc(cam, y[0], y[1])
    return dx is not None and dy is not None and math.hypot(dx[0] - dy[0], dx[1] - dy[1]) <= dx[2] + dy[2]


def _fault(track, info, id_, item, names, posed, joint, kind, need, f, m, o, clear) -> dict:
    t = (f - info["start"]) / info["fps"]
    mat = skin.transforms(skin.bones_of(item), track.fr.held(id_, f) / track.fr.fps, track.fr.stack)[joint]
    root = aim.point(track.fr.world(id_, f), aim.point(mat, [0.0, 0.0, 0.0]))
    lever = max(math.dist(root, posed[f][m][0]), 1e-3)
    deg = math.degrees(math.atan2(need, lever))
    part, into = names[posed[f][m][2]], names[posed[f][o][2]]
    if kind == "through":
        sid, what, by = "through_body", f"{id_}'s {part} passes {(need - CLEAR_M) * 100:.1f} cm into its {into}", CLEAR_M
    else:
        gap = clear - need
        sid, by = "touches_body", clear
        what = (f"{id_}'s {part} " + (f"comes {gap * 100:.1f} cm from" if gap >= 0.0005 else "touches") +
                f" its {into} at {t:.1f} s and they meet on the picture: the two read as one lump")
    what += f" (joint {names[joint]}; about {deg:.0f}° of turn away would clear it by {by * 100:.1f} cm)"
    return F.note(f"{sid}:{id_}.{names[joint]}", what, f"frame {f}, {t:.2f} s")
