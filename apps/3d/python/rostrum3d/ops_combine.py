"""Live booleans (SPEC §4.2): a `combine` item holds two or more solids and the core (Manifold) draws only the result.
The inputs stay items: move, turn or resize the cutter and the hole follows, because the result is made again from
the document every time it is drawn (quick view, Final and Render alike). `combine.set` (op, material, transform) is
the generated field operation (kind.py).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index, subtree_ids

from . import fields as F
from .kind import REGISTRY as R
from .ops_items import ID, NAME, new_item

OP = Param.choice("op", F.COMBINE_OPS, label="Operation", default="subtract",
                  help="union: join them · subtract: cut every later one out of the first · intersect: keep only "
                       "where all of them overlap")


@R.operation("combine.make", "Combine two or more solids (meshes or combines) into one live shape: union joins them, "
             "subtract cuts every later one out of the FIRST, intersect keeps where all overlap. The first target's "
             "place and name are taken by a new combine item holding the targets as its children, in order; they keep "
             "their transforms (now inside the combine) and are not drawn themselves. Move a child afterwards and the "
             "result follows. All targets must sit in the same list (same group or the top level).",
             target=F.SOLIDS, label="Combine",
             params=[OP, ID, NAME])
def combine_make(ctx, targets, args):
    if len(targets) < 2:
        ctx.fail(codes.BAD_ARGUMENT, "targets", f"are {len(targets)}; a combine needs two or more solids",
                 hint="Select the base first, then the cutters (Shift+click).")
    if len(set(targets)) != len(targets):
        ctx.fail(codes.BAD_ARGUMENT, "targets", "name the same item twice")
    locs = index(ctx.doc, ctx.kind.lists)
    base = locs[targets[0]]
    for t in targets[1:]:
        if (locs[t].parent, locs[t].key) != (base.parent, base.key):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f'is not in the same list as "{targets[0]}"',
                     hint="Move them into the same group first (item.arrange), so their positions mean the same.")
        if t in subtree_ids(base.item, ctx.kind.lists) or targets[0] in subtree_ids(locs[t].item, ctx.kind.lists):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f'is inside "{targets[0]}" or holds it')
    item = new_item(ctx, "combine", {"id": args.get("id"), "name": args.get("name") or base.item.get("name") or targets[0]},
                    {"op": args.get("op", "subtract"), "material": base.item.get("material", "")})
    ctx.insert(base.parent, base.key, item, base.index)
    for t in targets:
        ctx.move(t, item["id"], "children")
    return item
