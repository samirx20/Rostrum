"""Fixing joints and keying a whole pose (RIG.md › Operations, UX_SPEC 3.23): what the canvas's bone overlay does, as
operations an agent calls too.

- `rig.move_joint {bone, x, y}`: the bone's pivot (a joint, rig px, at rest) goes to (x, y). The parent's tip follows
  (its direction and length change so it still ends there), so do other bones that started at that joint; the
  bone's own tip stays, so its children don't move. With `end: "tip"` the bone's tip moves instead (the last joint of
  a chain: a hand's or a foot's end). Rest only: nothing posed changes, a bound layer stays where it is at rest.
- `rig.key {t}`: K on a rig: every bone's turn, scale and move and every IK chain's target and amount get a key at t
  with their values then (one change).
- `ik.pin {t, on}`: right-click a joint › Pin: the chain's target is held from t (a hold key on `pin`, RIG.md › pin).
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from ..evaluate import value_at
from ..kind import REGISTRY as R
from ..ops_keys import adds_nothing, put_key
from .model import tip
from .poses import POSED

NEAR = 0.5                                  # px: bones whose pivots are this close share a joint
TIME = dict(min=0, max=36000, unit="s")


def _aim(ctx, bone: dict, frm, to) -> None:
    """Set a bone's rest pivot, direction and length so it runs from `frm` to `to` (a zero length keeps its direction)."""
    ctx.set(bone["id"], "x", round(frm[0], 2))
    ctx.set(bone["id"], "y", round(frm[1], 2))
    if math.dist(frm, to) > 1e-6:
        ctx.set(bone["id"], "angle", round(math.degrees(math.atan2(to[1] - frm[1], to[0] - frm[0])), 2))
    ctx.set(bone["id"], "length", round(math.dist(frm, to), 2))


def rig_of(ctx, id_) -> dict:
    return ctx.item(index(ctx.doc, ctx.kind.lists)[id_].parent)


def move_joint(ctx, bone_id: str, x: float, y: float, end: str = "pivot") -> None:
    rig, bone = rig_of(ctx, bone_id), ctx.item(bone_id)
    bones = {b["id"]: b for b in rig["bones"]}
    new = (x, y)
    if end == "tip":
        was = tip(bone)
        _aim(ctx, bone, (bone["x"], bone["y"]), new)
        for b in bones.values():                # its children start where it now ends
            if b["parent"] == bone_id and math.dist((b["x"], b["y"]), was) < NEAR:
                _aim(ctx, b, new, tip(b))
        return
    old = (bone["x"], bone["y"])
    parent = bones.get(bone["parent"])
    if parent and math.dist(tip(parent), old) < NEAR:
        _aim(ctx, parent, (parent["x"], parent["y"]), new)
    for b in bones.values():                    # this bone and its brothers at the same joint
        if b["id"] == bone_id or (b["parent"] == bone["parent"] and math.dist((b["x"], b["y"]), old) < NEAR):
            _aim(ctx, b, new, tip(b))


@R.operation("rig.move_joint", "Move a joint of a rig at rest (rig px): the bone's pivot, its parent's tip and any bones "
             "starting there move; the bone's own tip stays. `end: tip` moves the bone's tip instead (the end of a hand or "
             "foot). Nothing posed changes.", target="bone", label="Move joint",
             params=[Param.number("x", label="X", required=True, min=-20000, max=20000, unit="px"),
                     Param.number("y", label="Y", required=True, min=-20000, max=20000, unit="px"),
                     Param.choice("end", ["pivot", "tip"], label="Which end", default="pivot")])
def rig_move_joint(ctx, targets, args):
    for t in targets:
        move_joint(ctx, t, args["x"], args["y"], args.get("end", "pivot"))


@R.operation("rig.key", "Key the rig's whole pose at a time: every bone's turn, scale and move, every IK chain's target "
             "and amount, with their values then (K on a rig).", target="rig", label="Key pose",
             params=[Param.number("t", label="At", default=0.0, **TIME)])
def rig_key(ctx, targets, args):
    at = args.get("t", 0.0)
    for t in targets:
        rig = ctx.item(t)
        for item in rig.get("bones", []) + rig.get("iks", []):
            for f in POSED[item["type"]]:
                if item["type"] == "ik" and item.get("mode", "ik") != "ik":
                    continue                    # an FK chain's target fields don't apply
                v = value_at(item, f, at)
                if not adds_nothing(item, f, v):    # the one K rule (ops_keys.adds_nothing): never a flat field
                    put_key(ctx, item["id"], f, at, {"v": v})


@R.operation("ik.pin", "Pin an IK chain's end where it is from a time on (a planted foot), or let it go: a hold key on "
             "`pin` (1 or 0).", target="ik", label="Pin",
             params=[Param.number("t", label="At", default=0.0, **TIME), Param.toggle("on", label="Pinned", default=True)])
def ik_pin(ctx, targets, args):
    for t in targets:
        if ctx.item(t).get("mode", "ik") != "ik":
            ctx.fail(codes.BAD_ARGUMENT, t, "is posed by FK", hint="Set its Pose by to IK first.")
        put_key(ctx, t, "pin", args.get("t", 0.0), {"v": 1.0 if args.get("on", True) else 0.0, "ease": "hold"})
