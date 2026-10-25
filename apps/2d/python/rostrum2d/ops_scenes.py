"""Scenes: copy one and put them in order (comp.add and comp.remove are in ops_items.py; renaming is item.rename).
The scene crumb's menu on screen and an agent call these same operations."""
from __future__ import annotations

from rostrum_core import Param, ids
from rostrum_core.errors import codes
from rostrum_core.tree import bare, child_keys, index

from .kind import REGISTRY as R
from .names import display_name, unique_name
from .ops_items import _all_ids, _names


@R.operation("comp.duplicate", "Copy scenes with everything in them (layers, keys, effects, masks under new ids); each copy "
             "lands right after its original, named \"<name> copy\".", target=("comp",), label="Duplicate scene",
             importance="secondary")
def comp_duplicate(ctx, targets, args):
    lists = ctx.kind.lists
    for t in targets:
        taken = set(_all_ids(ctx))
        loc = index(ctx.doc, lists)[t]

        def put(item, parent, key, at):
            new = {**bare(item, lists), "id": ids.counted(taken, item["type"])}
            taken.add(new["id"])
            ctx.insert(parent, key, new, at)
            for k in child_keys(item, lists):
                for child in item.get(k, []):
                    put(child, new["id"], k, None)
            return new["id"]

        copy = put(loc.item, loc.parent, loc.key, loc.index + 1)
        ctx.set(copy, "name", unique_name(_names(ctx), f"{display_name(loc.item)} copy"))


@R.operation("comp.move", "Put a scene at a place in the list of scenes (0 = first).", target=("comp",), label="Move scene",
             params=[Param.number("index", label="Position", min=0, max=100000, integer=True, required=True,
                                  help="0 = first scene")], importance="secondary")
def comp_move(ctx, targets, args):
    comps = ctx.doc.get("comps", [])
    if args["index"] >= len(comps):
        ctx.fail(codes.BAD_ARGUMENT, f'index {args["index"]}', f"is past the last scene (there are {len(comps)})",
                 hint=f"Use 0 to {len(comps) - 1}.")
    for t in targets:
        ctx.move(t, "root", "comps", args["index"])
