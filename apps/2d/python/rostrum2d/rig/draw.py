"""Drawing a bone by hand (UX_SPEC 3.23, the Bone tool J): `bone.draw {x, y, tipX, tipY}` adds one bone from a joint to
its tip (rig px, at rest). It hangs from the bone that ends at that joint (or `parent`, given), so clicks along an arm
make a chain; a joint that is another bone's start makes a branch beside it. Parts that have no bind yet attach by
themselves to the new bone when it runs through their middle at rest (an arm's bone through the arm, a head's
through the eyes and mouths too); the first bone through a part keeps it, and any part can be moved to another bone
later (Attach to bone, `bind.add` / `bind.set`). One call = one undo step.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes

from .. import boxes
from ..kind import REGISTRY as R
from ..names import display_name
from ..ops_items import ID, NAME, new_item
from .model import tip

NEAR = 2.0                                  # rig px: a start this close to a joint starts there
SHORT = 1.0                                 # rig px: a shorter bone is refused (a click, not a drag)


def joint_parent(bones: list, x: float, y: float) -> tuple[str, tuple[float, float]] | None:
    """(parent id, the joint) for a bone starting at (x, y): the bone ending there (a chain), else the parent of a bone
    starting there (a branch beside it). None: no joint there (a new root)."""
    for b in bones:
        if math.dist(tip(b), (x, y)) <= NEAR:
            return b["id"], tip(b)
    for b in bones:
        if math.dist((b["x"], b["y"]), (x, y)) <= NEAR:
            return b["parent"], (b["x"], b["y"])
    return None


def runs_through(box, a, b) -> bool:
    """The segment a → b passes through the middle of a box (x0, y0, x1, y1): within half its shorter side of its
    centre (a bone along an arm, not one that only grazes its end)."""
    c = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    dx, dy = b[0] - a[0], b[1] - a[1]
    k = max(0.0, min(1.0, ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / ((dx * dx + dy * dy) or 1.0)))
    return math.dist(c, (a[0] + k * dx, a[1] + k * dy)) <= max(2.0, min(box[2] - box[0], box[3] - box[1]) / 2)


def bone_name(bones: list) -> str:
    taken = {b["name"] for b in bones}
    return next(f"Bone {n}" for n in range(len(bones) + 1, len(bones) + 999) if f"Bone {n}" not in taken)


@R.operation("bone.draw", "Draw a bone on a rig from a joint (x, y) to its tip (tipX, tipY), rig px at rest. It hangs "
             "from the bone ending at that joint (a chain), else beside a bone starting there (a branch), else it is a "
             "root; `parent` overrides. Parts with no bind attach to it when it runs through them.",
             target="rig", label="Draw bone",
             params=[ID, NAME,
                     Param.number("x", label="Joint X", required=True, min=-20000, max=20000, unit="px"),
                     Param.number("y", label="Joint Y", required=True, min=-20000, max=20000, unit="px"),
                     Param.number("tipX", label="Tip X", required=True, min=-20000, max=20000, unit="px"),
                     Param.number("tipY", label="Tip Y", required=True, min=-20000, max=20000, unit="px"),
                     Param.id("parent", kind="bone", label="Parent bone", importance="secondary",
                              help='The bone it hangs from; "" = a root bone; left out = found from the joint'),
                     Param.toggle("attach", label="Attach parts", default=True, importance="secondary",
                                  help="Parts with no bind that it runs through follow it")])
def bone_draw(ctx, targets, args):
    if len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "target", "draw a bone on one rig at a time", targets)
    rig = ctx.item(targets[0])
    a, b = (args["x"], args["y"]), (args["tipX"], args["tipY"])
    found = joint_parent(rig["bones"], *a)
    if found:
        a = found[1]
    if math.dist(a, b) < SHORT:
        ctx.fail(codes.BAD_ARGUMENT, "tip", "is where the joint is", hint="Drag from the joint to where the bone ends.")
    parent = args["parent"] if args.get("parent") is not None else (found[0] if found else "")
    item = new_item(ctx, "bone", {**args, "name": args.get("name") or bone_name(rig["bones"])})
    item.update(parent=parent, x=round(a[0], 2), y=round(a[1], 2), length=round(math.dist(a, b), 2),
                angle=round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])), 2))
    ctx.insert(rig["id"], "bones", item)
    if not args.get("attach", True):
        return
    bound = {d["layer"] for d in rig["binds"]}
    for lay in rig.get("layers", []):
        if lay["id"] not in bound and runs_through(boxes.box(lay, 0.0), a, b):
            bind = new_item(ctx, "bind", {"name": f"{display_name(lay)} → {item['name']}"})
            bind.update(layer=lay["id"], bone=item["id"])
            ctx.insert(rig["id"], "binds", bind)
