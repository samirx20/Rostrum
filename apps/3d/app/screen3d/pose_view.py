"""Pose's drawing and hit maths, for pose_qt.py. No Qt.

A clay's bones posed at a time (skin.py's numbers, the ones the core bends the clay with), a drag in progress laid over
them (`turns`), projected through the viewport's view (gizmo.View) into parts of the viewport: a thin line per bone, a
small dot on each joint (a bone's head), a ring on each hold where its spot is now. What a press near a ring or a dot
means (screen px, CANVAS § 3.2: the same at any zoom), which bones a drag of one bone turns, and how far a bone bends
from its rest (the chip).
"""
from __future__ import annotations

import math

from rostrum3d import aim, skin

DOT_HIT = 7.5            # screen px either side of a joint dot (9 drawn, 15 hit)
RING_HIT = 9.0           # a hold ring (12 drawn, 18 hit)
LET_GO = 30.0            # a click on the held part this near its ring lets go; further along it holds another spot


def chain_of(clay: dict) -> list[tuple[dict, int]]:
    return skin.bones_of(clay)


def transforms(chain, t: float, turns: dict | None = None) -> list:
    """Each bone's transform in the clay's space at time t, the bones in `turns` turned that way instead."""
    if not turns:
        return skin.transforms(chain, t)
    out = []
    for bone, parent in chain:
        v = {k: float(bone.get(k, 0.0)) for k in ("x", "y", "z")}
        own = turns.get(bone["id"])
        m = skin.transforms([(bone, -1)], t)[0] if own is None else             aim.local({**v, **{k: float(own[k]) for k in skin.TURN}, "sx": 1.0, "sy": 1.0, "sz": 1.0})
        out.append(aim.compose(out[parent], m) if parent >= 0 else m)
    return out


def move_of(now, rest):
    """A bone's move from its rest: a rest spot on it to where it is now."""
    return aim.compose(now, aim.invert(rest))


def hold_spot(chain, now, rest, hold: dict):
    """A hold's spot now (clay space): its rest spot carried by its bone's move ({"at", "bone"}: pose_link.holds_of)."""
    i = next((k for k, (b, _) in enumerate(chain) if b["id"] == hold.get("bone")), -1)
    return list(hold["at"]) if i < 0 else aim.point(move_of(now[i], rest[i]), hold["at"])


def to_rest(chain, now, rest, bone: str, local):
    """A drawn spot on `bone` (clay space) back on the rest shape."""
    i = next((k for k, (b, _) in enumerate(chain) if b["id"] == bone), -1)
    return list(local) if i < 0 else aim.point(aim.invert(move_of(now[i], rest[i])), local)


def name_of(bone: dict) -> str:
    """The name the joint shows (its Plain or Humanoid name)."""
    return bone.get("name") or bone.get("joint") or bone["id"]


def moving(chain, bone: str, held: set[str]) -> list[str]:
    """The bones a drag of `bone` turns (pose.drag's rule): from it back towards the body, stopping at a held bone or
    an ancestor of one; with no holds the root never turns."""
    at = {b["id"]: k for k, (b, _) in enumerate(chain)}
    if bone not in at:
        return []
    fixed = set()
    for h in held:
        k = at.get(h, -1)
        while k >= 0:
            fixed.add(chain[k][0]["id"])
            k = chain[k][1]
    out, k = [], at[bone]
    while k >= 0 and chain[k][0]["id"] not in fixed and not (not held and chain[k][1] < 0):
        out.append(chain[k][0]["id"])
        k = chain[k][1]
    return out


def bend(bone: dict, turn: dict) -> float:
    """How far a bone turned from its rest, degrees (the angle of the one turn between the two)."""
    a = aim.local({**{k: float(bone.get(k, 0.0)) for k in skin.TURN}, "x": 0, "y": 0, "z": 0, "sx": 1, "sy": 1, "sz": 1})[0]
    b = aim.local({**{k: float(turn[k]) for k in skin.TURN}, "x": 0, "y": 0, "z": 0, "sx": 1, "sy": 1, "sz": 1})[0]
    tr = sum(a[r][c] * b[r][c] for r in range(3) for c in range(3))       # trace(aᵀ b)
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1) / 2))))


def chip(chain, grabbed: str, turns: dict) -> str:
    """The drag's chip: the grabbed part's name and its biggest bend ("forearm.R · 64°")."""
    bones = {b["id"]: b for b, _ in chain}
    if grabbed not in bones:
        return ""
    most = max((bend(bones[b], v) for b, v in turns.items() if b in bones), default=0.0)
    return f"{name_of(bones[grabbed])} · {most:.0f}°"


def overlay(clay: dict, holds: list[dict], world, view, t: float, w: float, h: float, lit=(),
            turns: dict | None = None) -> dict:
    """{lines: [{a, b, id, joint, lit}], dots: [{p, id, joint}], rings: [{p, bone, at}]} in parts of the viewport."""
    chain = chain_of(clay)
    now, rest = transforms(chain, t, turns), skin.transforms(chain)

    def at(p):
        q = view.project(aim.point(world, p))
        return None if q is None else [q[0] / w, q[1] / h]
    lines, dots = [], []
    for m, (bone, _) in zip(now, chain):
        s = skin.segment(m, bone)
        a, b = at(s[:3]), at(s[3:])
        if a and b:
            lines.append({"a": a, "b": b, "id": bone["id"], "joint": bone.get("joint", ""), "lit": bone["id"] in lit})
            dots.append({"p": a, "id": bone["id"], "joint": name_of(bone)})
    rings = [{"p": p, "bone": hd["bone"], "at": hd["at"]} for hd in holds if (p := at(hold_spot(chain, now, rest, hd)))]
    return {"lines": lines, "dots": dots, "rings": rings}


def near(points: list[dict], x: float, y: float, w: float, h: float, reach: float) -> int:
    """The index of the nearest of `points` ({p} in parts) within `reach` px of (x, y) px, else -1."""
    best, k = reach, -1
    for i, d in enumerate(points):
        dist = math.hypot(d["p"][0] * w - x, d["p"][1] * h - y)
        if dist <= best:
            best, k = dist, i
    return k

