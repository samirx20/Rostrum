"""`mesh.mirror`: give a mesh a mirrored copy across a clay's mirror (mirror.py). Placing a part on a clay whose Mirror
is on does it in the same step (the screen's Place on a surface, the script's `place_on`, MCP `edit_place_on`).
"""
from __future__ import annotations

from rostrum_core import Param, ids
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import build, mirror
from .kind import REGISTRY as R
from .ops_items import refuse_used_id


@R.operation("mesh.mirror", "Give a mesh a mirrored copy on the other side of a clay's mirror (its own X = 0 plane, the "
             "one Mirror sculpts across). The copy follows the original: its shape, material, keys and place are the "
             "original's, reflected; edits sent to the copy go to the original; deleting the original or the clay "
             "deletes the copy.", target="mesh", label="Mirrored copy", importance="secondary",
             params=[Param.id("on", label="Across clay", required=True, help="The clay whose mirror the copy is across"),
                     Param.text("id", label="Id", help="The copy's id; <mesh>_mirrored when left out")])
def mesh_mirror(ctx, targets, args):
    clay = ctx.item(args["on"])
    if clay["type"] != "clay":
        ctx.fail(codes.BAD_ARGUMENT, f'on "{args["on"]}"', f"is a {clay['type']}, not a clay")
    if args.get("id") and len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, '"id"', "can only be given when one mesh gets a copy")
    for t in targets:
        orig = ctx.item(t)
        if orig.get("mirror"):
            ctx.fail(codes.BAD_ARGUMENT, t, f'is itself the mirrored copy of {orig["mirror"]}',
                     hint=f'Give {orig["mirror"]} the copy, or none: it has one.')
        taken = index(ctx.doc, ctx.kind.lists)
        if mirror.copies_of((loc.item for loc in taken.values() if loc.item.get("mirrorOn") == args["on"]), [t]):
            ctx.fail(codes.BAD_ARGUMENT, t, f"already has a mirrored copy across {args['on']}")
        new = args.get("id") or (f"{t}_mirrored" if f"{t}_mirrored" not in taken else ids.counted(taken, f"{t}_mirrored"))
        refuse_used_id(ctx, new)
        copy = build.make("mesh", new, {"name": f'{orig.get("name") or t}{mirror.SUFFIX}', **mirror.stored(orig),
                                        "mirror": t, "mirrorOn": args["on"]}, ctx.where)
        loc = taken[t]
        ctx.insert(loc.parent, loc.key, copy, loc.index + 1)
