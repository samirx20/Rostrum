"""fused:<clay>.<a>~<b>, a pose fault (pose_faults.py): two lumps of a figure, at balls riding parts that are not neighbours (the head
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

TRUNK = ("body", "chest")  # a limb against the trunk it hangs from is joined on purpose
REACH = 1.0             # parts closer than this share of the larger blend are webbed: the smooth join adds clay wherever
                         # both surfaces are within the blend (gaps7 Hello: the upper arm 3.75 cm from the head under its 4 cm blend)
MARGIN = 0.5             # the fix's blend: this share of the gap (a blend just under the gap still rounds the two together)
AWAY_M = 0.005           # the fix's move clears the blend by this


def fused(track, info, id_, item, balls, keyed) -> list[dict]:
    par, names, pieces = PB.parents(item), PB.joint_names(item), PB.rest_pieces(item)
    trunk = {n for n, up in enumerate(par) if up < 0 or names[n] in TRUNK}
    steps: dict[tuple, tuple] = {}           # (lump, bone) pair -> the closest (gap, ball i, ball j)
    for i, (p, ri, a) in enumerate(balls):
        for j, (q, rj, b) in enumerate(balls):
            ki, kj = (pieces[i][2], a), (pieces[j][2], b)
            if ki[0] < kj[0]:
                gap = math.dist(p, q) - ri - rj
                if (ki, kj) not in steps or gap < steps[(ki, kj)][0]:
                    steps[(ki, kj)] = (gap, i, j)
    out, seen = [], set()
    for (ki, kj), (gap, i, j) in sorted(steps.items(), key=lambda x: x[1][0]):
        pa, pb = ki[1], kj[1]
        joint = next((n for n in mover(par, keyed, pa, pb) if n is not None), None)
        if gap < 0 or pa == pb or pa in trunk or pb in trunk or joint is None or (ki[0], kj[0]) in seen:
            continue                         # overlapping, or a limb on the trunk it hangs from: joined on purpose
                                             # (not the hierarchy: a web can make the finder hang an arm from the head)
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
            f"joins them and stretches when {names[joint]} moves, so they read as one lump" + _hung(par, names, pa, pb),
            f"lower {lower}; or move the {moving} {(blend - gap + AWAY_M) * 100:.1f} cm away from the {still}; "
            "if they are meant to be one lump, keep it", "at rest"))
    return out


def _hung(par, names, a, b) -> str:
    """The web made the joint finder hang one part from the other (gaps7 r1: both arms from the head, so a head turn swung them)."""
    if par[b] == a or par[a] == b:
        child, up = (b, a) if par[b] == a else (a, b)
        return f"; it even made the joints hang {names[child]} from the {names[up]}, so turning the {names[up]} swings it"
    return ""


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
