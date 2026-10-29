"""The animation layer operations (layers.py), for any app with layers (`register_layer_ops`): animlayer.add,
animlayer.set (name, weight, mode, on; a weight at a time keys it, so a layer fades), animlayer.remove (its keys go
with it) and animlayer.move (its place in the stack). Each is one change, one undo step. Keys go on a layer through
key.add's `layer` (register_key_ops(…, layers=True)).
"""
from __future__ import annotations

from ..errors import codes
from ..params import Param
from ..tree import walk
from .layers import FIELD, LIST, MODES, TYPE, stack_of
from .marked import id_part, same_time

NAME = Param.text("name", label="Name")
MODE = Param.choice("mode", list(MODES), label="Mode", labels={"add": "Add", "replace": "Replace"},
                    help="add: its keys are offsets added on top (a breath over a walk); replace: the value moves toward "
                    "its keys by the weight")
WEIGHT = Param.number("weight", label="Weight", min=0, max=1, step=0.01,
                      help="How much of the layer shows: 0 none, 1 all of it")
ON = Param.toggle("on", label="On", help="Off: the layer is kept but not applied")
AT = Param.number("at", label="At", min=-36000, max=36000, unit="s",
                  help="With weight: key the weight at this time (the layer fades between its weight keys)")


def register_layer_ops(registry, lists_of=lambda ctx: ctx.kind.lists) -> None:
    """Register the four animLayer operations on `registry` (the app's LISTS include layers.with_lists)."""

    @registry.operation("animlayer.add", "Make an animation layer on top of the stack: a move laid over the Base "
                        "(a breath over a walk). Then key.add with `layer` puts keys on it.",
                        label="New layer", params=[Param.text("id", label="Id"), NAME, MODE, WEIGHT])
    def layer_add(ctx, targets, args):
        id_ = args.get("id") or ctx.new_id(TYPE)
        if id_ in ctx.idx:
            ctx.fail(codes.CONFLICT, f'id "{id_}"', "is already used", hint="Give another id, or leave it out.")
        n = len(stack_of(ctx.doc)) + 1
        ctx.insert("root", LIST, {"id": id_, "type": TYPE, "name": args.get("name") or f"Layer {n}",
                                  "weight": float(args.get("weight", 1.0)), "mode": args.get("mode", "add"), "on": True})

    @registry.operation("animlayer.set", "Rename a layer, set its weight (with `at`: a weight key, so it fades), its "
                        "mode (add / replace) or switch it on / off.", target=TYPE, label="Edit layer",
                        params=[NAME, WEIGHT, AT, MODE, ON])
    def layer_set(ctx, targets, args):
        if "at" in args and "weight" not in args:
            ctx.fail(codes.BAD_ARGUMENT, '"at"', "keys the weight", hint="Give weight too.")
        for t in targets:
            for k in ("name", "mode", "on"):
                if k in args:
                    ctx.set(t, k, args[k])
            if "weight" in args:
                _weight(ctx, ctx.item(t), float(args["weight"]), args.get("at"))

    def _weight(ctx, layer: dict, w: float, at):
        keys = [k for k in layer.get("keys", []) if k.get("prop") == "weight"]
        if at is None and keys:
            ctx.fail(codes.BAD_ARGUMENT, '"at"', f"is needed: {layer['id']}'s weight has keys", hint="Give the time.")
        if at is None:
            return ctx.set(layer["id"], "weight", w)
        if there := next((k for k in keys if same_time(k["t"], at)), None):
            return ctx.set(there["id"], "v", w)
        ctx.insert(layer["id"], "keys", {"id": f"{layer['id']}.weight.{id_part(at)}", "type": "key", "prop": "weight",
                                         "t": at, "v": w, "ease": "smooth"})

    @registry.operation("animlayer.remove", "Delete animation layers and every key on them (the Base stays).",
                        target=TYPE, label="Delete layer", importance="secondary")
    def layer_remove(ctx, targets, args):
        gone = set(targets)
        ctx.remove_many([*(i["id"] for i in walk(ctx.doc, lists_of(ctx)) if i.get("type") == "key" and i.get(FIELD) in gone),
                         *targets])

    @registry.operation("animlayer.move", "Move a layer in the stack: `to` 0 is the bottom (laid first, just over the "
                        "Base); higher layers lay over it.", target=TYPE, label="Move layer", importance="secondary",
                        params=[Param.number("to", label="To", min=0, max=999, step=1, required=True)])
    def layer_move(ctx, targets, args):
        for t in targets:
            ctx.move(t, "root", LIST, min(int(args["to"]), len(stack_of(ctx.doc)) - 1))
