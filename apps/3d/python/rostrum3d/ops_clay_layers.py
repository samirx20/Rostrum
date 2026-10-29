"""Sculpt layer operations (PR4; clay_layers.py): make a layer (the next strokes go on it), remove one (with its
strokes), and Bake (its strokes join the Base at the Amount they show). A layer's Name, Amount and On are
`claylayer.set`; which layer the next stroke goes on is `clay.set sculptLayer` ("" = the Base). Each is one undo step.
"""
from __future__ import annotations

from rostrum_core import Param, ids
from rostrum_core.errors import codes

from . import build, clay_layers as L
from .kind import REGISTRY as R


def _clay(ctx, t: str) -> dict:
    item = ctx.item(t)
    if item["type"] != "clay":
        ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f"is a {item['type']}, not a clay")
    return item


def _clay_of(ctx, layer_id: str) -> dict:
    return next(c for c in _clays(ctx.doc) if any(lay["id"] == layer_id for lay in L.layers(c)))


def _clays(doc) -> list[dict]:
    out, stack = [], list(doc.get("items", []))
    while stack:
        it = stack.pop()
        out += [it] if it.get("type") == "clay" else []
        stack += it.get("children", [])
    return out


@R.operation("claylayer.add", "Make a sculpt layer on a clay: a group of strokes with an Amount (a smile, a frown, a "
             "blink). The strokes and pieces made after it go on it until clay.set sculptLayer changes (\"\" = the "
             "Base). Layers are applied after every Base step, each at its Amount (0 = as if it weren't there).",
             target="clay", label="New sculpt layer",
             params=[Param.text("name", label="Name", help='"smile", "frown"; "Layer N" when left out'),
                     Param.number("amount", label="Amount", min=0, max=1, default=1.0)])
def claylayer_add(ctx, targets, args):
    for t in targets:
        clay = _clay(ctx, t)
        name = args.get("name") or f"Layer {len(L.layers(clay)) + 1}"
        values = {"name": name, "amount": args.get("amount", 1.0)}
        layer = build.make("claylayer", ids.counted(ctx.idx, f"{t}.layer"), values, ctx.where)
        ctx.insert(t, L.LIST, layer)
        ctx.set(t, L.NEXT, layer["id"])


@R.operation("claylayer.remove", "Remove sculpt layers and every stroke and piece on them; the clay is rebuilt without "
             "them (claylayer.bake keeps their strokes in the Base instead).", target="claylayer", label="Remove layer")
def claylayer_remove(ctx, targets, args):
    for t in targets:
        clay = _clay_of(ctx, t)
        for s in [s for s in clay.get("steps", []) if s.get(L.STEP_FIELD) == t]:
            ctx.remove(s["id"])
        if clay.get(L.NEXT) == t:
            ctx.set(clay["id"], L.NEXT, "")
        ctx.remove(t)


@R.operation("claylayer.bake", "Bake sculpt layers into the Base: their strokes join the Base at the strength they "
             "show now (Amount × strength; a ball's radius likewise) and the layers go.", target="claylayer",
             label="Bake layer")
def claylayer_bake(ctx, targets, args):
    for t in targets:
        clay = _clay_of(ctx, t)
        a = L.amounts(clay).get(t, 0.0)
        for s in [s for s in clay.get("steps", []) if s.get(L.STEP_FIELD) == t]:
            ctx.remove(s["id"])
            if a > 0:          # last in the list: still after every Base step and before the layers below, as it was
                done = {**L.scaled(s, a), L.STEP_FIELD: ""}
                ctx.insert(clay["id"], "steps", {k: round(v, 6) if k in ("strength", "radius") else v
                                                 for k, v in done.items()})
        if clay.get(L.NEXT) == t:
            ctx.set(clay["id"], L.NEXT, "")
        ctx.remove(t)
