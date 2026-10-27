"""Follow and stick as one step each (SPEC §8): `follow.add` picks the items up on another item (from a time, until a
time), `follow.release` lets them go at a time, `stick.add` stands them on a mesh's surface. They write the same
fields a person sets in the Follow and Stick groups (follow, followAmount keys, stick: follow.py resolves them), so
one undo takes each back and the panel shows what an agent did.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import fields as F
from .kind import REGISTRY as R
from .ops_keys import put_key

ITEM = Param.text("item", label="Item", required=True, kind="item", help="The id of the item to follow or stick to")
FROM = Param.number("from", label="From", min=0, max=36000, unit="s",
                    help="Picked up at this time (it stands still before). Left out: it rides from the start")
UNTIL = Param.number("until", label="Until", min=0, max=36000, unit="s",
                     help="Let go at this time: it stays where it is then. Left out: it rides to the end")
AT = Param.number("at", label="At", min=0, max=36000, unit="s", required=True, help="The time, in seconds")
HEIGHT = Param.number("height", label="Height", min=-1e5, max=1e5, unit="m",
                      help="How far above the surface its Position stands (its Y). Left out: 0, on the surface")
POSE = Param.toggle("pose", label="Follow the pose", help="Ride the bone of the posed clay (or mesh with bones) "
                     "nearest where it sits, so it bends with the pose there (an eye on a face). Default: the whole item")
MOVABLE = tuple(t for t in F.ITEMS if F.param(t, "follow"))       # what can follow or stick (not a rig)


def _target(ctx, targets, args, need_mesh=False):
    id_ = args["item"]
    loc = ctx.idx.get(id_)
    if loc is None or loc.item.get("type") not in F.ITEMS:
        ctx.fail(codes.BAD_ARGUMENT, "item", f'"{id_}" is not an item in the scene')
    if need_mesh and loc.item["type"] != "mesh":
        ctx.fail(codes.BAD_ARGUMENT, "item", f'"{id_}" is a {loc.item["type"]}; things stick only to a mesh')
    if id_ in targets:
        ctx.fail(codes.BAD_ARGUMENT, "item", f'"{id_}" can\'t follow or stick to itself')
    return id_


def _amount(ctx, id_: str, t: float, value: float):
    put_key(ctx, id_, "followAmount", t, {"v": value, "ease": "hold"})


@R.operation("follow.add", "Make the items ride on another item (a bud on an opening lid): they move and turn with it "
             "from where they stand. With `from` / `until` they are picked up and let go then (followAmount keyed "
             "1 and 0, held): let go, they stay where they are, never jumping back. `pose`: on a posed clay, ride the "
             "bone nearest where each sits (an eye stays on a turning head); a mirrored copy rides its own side.",
             target=MOVABLE, label="Follow", params=[ITEM, FROM, UNTIL, POSE])
def follow_add(ctx, targets, args):
    target = _target(ctx, targets, args)
    start, end = args.get("from"), args.get("until")
    if start is not None and end is not None and end <= start:
        ctx.fail(codes.BAD_ARGUMENT, "until", f"is at {end} s, not after from ({start} s)")
    for t in targets:
        ctx.set(t, "follow", target)
        if args.get("pose") or ctx.item(t).get("followPose"):
            ctx.set(t, "followPose", bool(args.get("pose")))
        if start:
            _amount(ctx, t, 0.0, 0.0)
            _amount(ctx, t, start, 1.0)
        elif end is not None:
            _amount(ctx, t, 0.0, 1.0)
        if end is not None:
            _amount(ctx, t, end, 0.0)


@R.operation("follow.release", "Let following items go at `at`: they stay where they are then (followAmount keyed 0, "
             "held). Their follow stays set, so a later key of 1 picks them up again.",
             target=MOVABLE, label="Let go", params=[AT], valid_when=F.FOLLOWS)
def follow_release(ctx, targets, args):
    for t in targets:
        if not ctx.item(t).get("keys") or not any(k["prop"] == "followAmount" for k in ctx.item(t)["keys"]):
            _amount(ctx, t, 0.0, 1.0)                         # it rode until now
        _amount(ctx, t, args["at"], 0.0)


@R.operation("stick.add", "Stand the items on a mesh's surface straight below them as they move (a plane, disc, box, "
             "sphere, cylinder, cone, capsule or editable mesh): their Y becomes their height above it.",
             target=MOVABLE, label="Stick to surface", params=[ITEM, HEIGHT])
def stick_add(ctx, targets, args):
    target = _target(ctx, targets, args, need_mesh=True)
    for t in targets:
        ctx.set(t, "stick", target)
        ctx.set(t, "y", args.get("height", 0.0))
