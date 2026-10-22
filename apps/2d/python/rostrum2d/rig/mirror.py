"""Mirror pose (UX_SPEC 3.23, pose library): `pose.mirror {t, how}` keys the right side of a rig from its left side
at a time (or right from left, or swaps the two). Sides are read from names ("upper arm L", "Forearm_R", "leftHand",
`bodynames.part`'s words); a bone whose own name has no side takes its bound parts' side ("Bone 3" bound to "hand L").
Two items pair when their names match with the side words taken out.

Mirrored across the up-down line: a turn changes sign, a sideways move changes sign, scale and an up-down move stay;
an IK target keeps its offset from its own chain's rest tip, mirrored sideways; IK amount and a swap set's drawing are
copied. With `how: swap` the middle bones (no side) turn the other way too: the whole pose seen in a mirror.
One call = one undo step; like Apply pose it only puts keys at `t`.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from ..evaluate import value_at
from ..kind import REGISTRY as R
from ..ops_keys import keys_of, put_key
from .bodynames import SIDES, tokens
from .model import tip
from .poses import TIME, owners

FLIP = {"rotation": -1.0, "moveX": -1.0}          # pose fields that change sign in a mirror (others are copied)
HOW = ["left_to_right", "right_to_left", "swap"]


def side_of(name: str) -> tuple[str, str]:
    """(side "L" / "R" / "", the name without its side words) of an item's name."""
    words = tokens(name)
    side = next((SIDES[w] for w in words if w in SIDES), "")
    return side, " ".join(w for w in words if w not in SIDES)


def sides(rig: dict) -> dict[str, tuple[str, str]]:
    """{item id: (side, pair key)} of every bone, IK chain and swap set of the rig."""
    layer_names = {}
    stack = list(rig.get("layers", []))
    while stack:
        lay = stack.pop()
        layer_names[lay["id"]] = lay.get("name", "")
        stack += lay.get("layers", [])
    out = {}
    for id_, (item, _) in owners(rig).items():
        side, key = side_of(item.get("name", ""))
        if not side and item["type"] == "bone":          # a hand-drawn "Bone 3": the side of the parts it moves
            parts = sorted(side_of(layer_names.get(b["layer"], "")) for b in rig.get("binds", []) if b["bone"] == id_)
            if len({s for s, _ in parts} - {""}) == 1 and all(s for s, _ in parts):
                side, key = parts[0][0], "of " + parts[0][1]
        out[id_] = (side, f'{item["type"]}:{key}')
    return out


def pairs(rig: dict) -> list[tuple[str, str]]:
    """(left id, right id) of the items that mirror each other."""
    found = sides(rig)
    right = {key: id_ for id_, (s, key) in found.items() if s == "R"}
    return [(id_, right[key]) for id_, (s, key) in found.items() if s == "L" and key in right]


def mirrored(rig: dict, src: str, dst: str, t: float) -> dict:
    """{field: value} for `dst` mirroring `src`'s pose at t."""
    items = owners(rig)
    (a, fields), (b, _) = items[src], items[dst]
    out = {}
    for f in fields:
        v = value_at(a, f, t)
        if a["type"] == "ik" and f in ("targetX", "targetY"):
            ra, rb = _rest_tip(rig, a), _rest_tip(rig, b)
            i = 0 if f == "targetX" else 1
            v = rb[i] + (ra[i] - v if i == 0 else v - ra[i])
        out[f] = v * FLIP.get(f, 1.0)
    return out


def _rest_tip(rig: dict, ik: dict):
    return tip(next(b for b in rig["bones"] if b["id"] == ik["bone"]))


def plan(rig: dict, t: float, how: str = "left_to_right") -> dict[str, dict]:
    """{item id: {field: value}}: what Mirror pose keys at t."""
    out = {}
    for left, right in pairs(rig):
        if how in ("left_to_right", "swap"):
            out[right] = mirrored(rig, left, right, t)
        if how in ("right_to_left", "swap"):
            out[left] = mirrored(rig, right, left, t)
    if how == "swap":
        for id_, (side, _) in sides(rig).items():
            item, fields = owners(rig)[id_]
            if not side and item["type"] == "bone":
                out[id_] = {f: value_at(item, f, t) * FLIP[f] for f in fields if f in FLIP}
    return out


@R.operation("pose.mirror", "Mirror the rig's pose at a time: key the right side from the left (left_to_right), the "
             "left from the right, or swap them (the whole pose seen in a mirror). Sides come from names (L / R, left / "
             "right).", target="rig", label="Mirror pose",
             params=[TIME, Param.choice("how", HOW, label="Which way", default="left_to_right",
                                        help="left_to_right copies the left side onto the right")])
def pose_mirror(ctx, targets, args):
    at, how = args.get("t", 0.0), args.get("how", "left_to_right")
    for t in targets:
        rig = ctx.item(t)
        goal = plan(rig, at, how)
        if not goal:
            ctx.fail(codes.BAD_ARGUMENT, t, "has no left and right parts to mirror",
                     hint='Name the bones or their parts with L / R or left / right ("arm L", "hand R").')
        for id_, values in goal.items():
            item = ctx.item(id_)
            for f, v in values.items():
                v = round(v, 4) + 0.0           # never "-0"
                if not keys_of(item, f) and abs(value_at(item, f, at) - v) < 1e-9:
                    continue                     # already so, and still: no key needed
                put_key(ctx, id_, f, at, {"v": v, "ease": "hold" if f == "show" else "smooth"})
