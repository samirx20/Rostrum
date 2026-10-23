"""Things placed in time on a track: notes, drum hits and recorded clips. One maker registers each type's
`.add`, `.set`, `.remove` (and `.add_many` for notes and hits: a whole phrase in one call, one undo step)."""
from __future__ import annotations

from rostrum_core import Param, codes

from . import fields as FD
from . import ids
from . import values as V
from .ops_group import clip_set
from .registry import REGISTRY, set_fields, taken

ID = Param.text("id", label="Id", help="Optional; made from where it starts when left out.")
LABELS = {"note": "note", "hit": "drum hit", "clip": "clip"}


def _new_id(type_, track, args, ctx):
    have = taken(ctx)
    if args.get("id"):
        if args["id"] in have:
            ctx.fail(codes.BAD_ARGUMENT, f'id "{args["id"]}"', "is already used in this document")
        return args["id"]
    if type_ == "note":
        return ids.note(track, args["at"], ctx.doc, have, ctx.where)
    if type_ == "hit":
        return ids.hit(track, args["drum"], args["at"], ctx.doc, have, ctx.where)
    return ids.clip(track, args["at"], ctx.doc, have, ctx.where)


def _adder(type_, key):
    def add(ctx, track, args):
        args = dict(args)
        id_ = _new_id(type_, track, args, ctx)
        args.pop("id", None)
        ctx.insert(track, key, {"id": id_, "type": type_, **FD.DEFAULTS[type_], **args})
    return add


def register(type_, key, many=False):
    label, add = LABELS[type_], _adder(type_, key)
    add_params = [ID, *FD.params(type_, required=True)]

    @REGISTRY.operation(f"{type_}.add", f"Add a {label} to tracks.", target="track", params=add_params,
                        label=f"Add {label}")
    def add_one(ctx, targets, args):
        for t in targets:
            add(ctx, t, args)

    if many:
        rule, schema = V.fields_of(add_params, label)
        batch = V.listof(f"{type_}s", rule, schema, required=True, help=f"The {label}s, each like {type_}.add's "
                         "arguments.")

        @REGISTRY.operation(f"{type_}.add_many", f"Add many {label}s to a track in one step.", target="track",
                            params=[batch], label=f"Add {label}s")
        def add_many(ctx, targets, args):
            for t in targets:
                for one in args[f"{type_}s"]:
                    add(ctx, t, one)

    REGISTRY.operation(f"{type_}.set", f"Change {label}s." + (" A layered one carries its group." if type_ == "clip" else ""),
                       target=type_, params=FD.params(type_), label=f"Edit {label}", fields=True)(
        clip_set if type_ == "clip" else set_fields)

    @REGISTRY.operation(f"{type_}.remove", f"Delete {label}s.", target=type_, label=f"Delete {label}",
                        importance="secondary")
    def remove(ctx, targets, args):
        for t in targets:
            ctx.remove(t)


register("note", "notes", many=True)
register("hit", "hits", many=True)
register("clip", "clips")
