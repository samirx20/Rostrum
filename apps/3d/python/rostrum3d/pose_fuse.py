"""fused:<clay>.<a>~<b>, a pose fault (pose_faults.py): two lumps of a figure on parts that are not neighbours (the head
and an arm, an arm and a leg) that don't touch at rest but are closer than REACH of the larger of their blends, so the smooth
join builds a web of clay between them (gaps7 Hello: the shoulder 1 cm under the head's 4 cm blend; raised, the arm
"melts into the side of the head"). The clay is meshed once at rest and bent by bones, so the web stretches with the
pose. Fires only when a keyed joint moves the two apart; a still web is just shape. Lumps that overlap at rest are
joined on purpose (an arm into the body) and stay silent. The fix: lower the blend under the gap, or move a lump away.
"""
from __future__ import annotations

import math

from rostrum_core.mcp import faults as F

from . import pose_body as PB
from .pose_touch import mover

REACH = 0.75            # lumps closer than this share of the larger blend are webbed (a 2.6 cm gap under a 2.75 cm
                         # blend, the default head on SHAPE's arm, shows no web; 1 cm under 4 cm melts: gaps7 Hello)
MARGIN = 0.8             # the fix's blend: this share of the gap
AWAY_M = 0.005           # the fix's move clears the blend by this


def fused(track, info, id_, item, balls, keyed) -> list[dict]:
    par, names, pieces = PB.parents(item), PB.joint_names(item), PB.rest_pieces(item)
    near = lambda a, b: a == b or par[a] == b or par[b] == a                       # noqa: E731
    sides = _sides(balls, pieces)
    steps: dict[tuple, tuple] = {}           # (lump, side) pair -> the closest (gap, ball i, ball j)
    for i, (p, ri, _) in enumerate(balls):
        for j, (q, rj, _) in enumerate(balls):
            ki, kj = (pieces[i][2], _side(p)), (pieces[j][2], _side(q))
            if ki[0] < kj[0]:
                gap = math.dist(p, q) - ri - rj
                if (ki, kj) not in steps or gap < steps[(ki, kj)][0]:
                    steps[(ki, kj)] = (gap, i, j)
    out, seen = [], set()
    for (ki, kj), (gap, i, j) in sorted(steps.items(), key=lambda x: x[1][0]):
        pa, pb = sides[ki], sides[kj]
        joint = next((n for n in mover(par, keyed, pa, pb) if n is not None), None)
        if gap < 0 or near(pa, pb) or pa in _moved(par, pb) or pb in _moved(par, pa) or joint is None or (ki[0], kj[0]) in seen:
            continue                         # overlapping, or a limb on the trunk it hangs from: joined on purpose
        seen.add((ki[0], kj[0]))
        (na, ba, _), (nb, bb, _) = pieces[i], pieces[j]
        blend = max(ba, bb)
        if gap >= REACH * blend:
            continue
        a, b = na or names[pa], nb or names[pb]
        moving, still = (b, a) if pb in _moved(par, joint) else (a, b)
        wide = [n for n, bl in ((a, ba), (b, bb)) if bl > gap * MARGIN]
        lower = " and ".join(f'{w}\'s blend to {gap * MARGIN * 100:.1f} cm (c.lump(…, name="{w}", blend={gap * MARGIN:.3f}))'
                             for w in wide)
        out.append(F.fault(
            f"fused:{id_}.{a}~{b}",
            f"{id_}'s {a} and {b} are {gap * 100:.1f} cm apart at rest, inside the {blend * 100:.1f} cm blend: a web of clay "
            f"joins them and stretches when {names[joint]} moves, so they read as one lump",
            f"lower {lower}; or move the {moving} {(blend - gap + AWAY_M) * 100:.1f} cm away from the {still}; "
            "if they are meant to be one lump, keep it", "at rest"))
    return out


def _side(p) -> int:
    return (p[0] > 1e-6) - (p[0] < -1e-6)


def _sides(balls, pieces) -> dict:
    """(lump, side of the middle) -> the bone most of its balls ride: the part that lump is."""
    count: dict = {}
    for (p, _, b), (_, _, s) in zip(balls, pieces):
        count.setdefault((s, _side(p)), {}).setdefault(b, 0)
        count[(s, _side(p))][b] += 1
    return {k: max(v, key=v.get) for k, v in count.items()}


def _moved(par, joint) -> set[int]:
    """The bones a joint carries: itself and everything below it."""
    out, grew = {joint}, True
    while grew:
        grew = False
        for n, p in enumerate(par):
            if p in out and n not in out:
                out.add(n)
                grew = True
    return out
