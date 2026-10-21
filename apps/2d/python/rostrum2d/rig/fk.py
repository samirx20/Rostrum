"""A rig's bones posed by FK at time t, in Python (RIG.md › Evaluation 1): the same rule as the engine's
`engine/render/src/rig/pose.rs`, used only where Python must know where a joint is before the engine draws (a long IK
chain's base, chain.py). The engine stays the one that draws; test_rig_chain.py checks the two agree.

A frame is an affine (a, b, c, d, e, f): p' = (a·x + c·y + e, b·x + d·y + f), y down, degrees clockwise on screen.
"""
from __future__ import annotations

import math

from rostrum_core.keys import keys_of, track_value

ID = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mul(m, n):
    a, b, c, d, e, f = m
    p, q, r, s, t, u = n
    return (a * p + c * q, b * p + d * q, a * r + c * s, b * r + d * s, a * t + c * u + e, b * t + d * u + f)


def rot(deg):
    s, c = math.sin(math.radians(deg)), math.cos(math.radians(deg))
    return (c, s, -s, c, 0.0, 0.0)


def move(x, y):
    return (1.0, 0.0, 0.0, 1.0, x, y)


def inverse(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * e + ic * f), -(ib * e + id_ * f))


def apply(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def field(bone: dict, prop: str, t: float, baked: dict, default: float) -> float:
    """A bone field at t: the scene's baked keys first (an expression), then its own keys, then its value."""
    keys = baked.get(bone["id"], {}).get(prop) or keys_of(bone, prop)
    return float(track_value(keys, t)) if keys else float(bone.get(prop, default))


def depth(bones: dict, id_: str) -> int:
    d, cur = 0, bones[id_].get("parent", "")
    while cur and cur in bones and d <= len(bones):
        d, cur = d + 1, bones[cur].get("parent", "")
    return d


def pose(rig: dict, t: float, baked: dict | None = None, turns: dict | None = None) -> dict:
    """{bone id: (rest frame, posed frame, length)} at t, FK only. `turns`: extra degrees added to bones' rotation."""
    baked, turns = baked or {}, turns or {}
    bones = {b["id"]: b for b in rig.get("bones", [])}
    out = {}
    for id_ in sorted(bones, key=lambda i: depth(bones, i)):
        b = bones[id_]
        rest = mul(move(b.get("x", 0.0), b.get("y", 0.0)), rot(b.get("angle", 0.0)))
        parent = out.get(b.get("parent", ""))
        world_p, rest_p = (parent[1], parent[0]) if parent else (ID, ID)
        local = mul(inverse(rest_p), rest)
        s = field(b, "scale", t, baked, 1.0)
        turn = field(b, "rotation", t, baked, 0.0) + turns.get(id_, 0.0)
        world = mul(mul(mul(mul(world_p, move(field(b, "moveX", t, baked, 0.0), field(b, "moveY", t, baked, 0.0))),
                            local), rot(turn)), (s, 0.0, 0.0, s, 0.0, 0.0))
        out[id_] = (rest, world, float(b.get("length", 100.0)))
    return out


def pivot(posed) -> tuple[float, float]:
    return posed[1][4], posed[1][5]


def tip(posed) -> tuple[float, float]:
    return apply(posed[1], (posed[2], 0.0))
