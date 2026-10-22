"""layer.stagger: layers start one after another (UX_SPEC 3.19 Stagger). The layers are put in an order, then each
moves in time (with its keys, effects, drawings: layer.shift's way) so it starts `by` seconds after the one before,
counting from the earliest start among them. Staggering again re-spreads from there, so it can be changed at will.
key.stagger does the same with picked keys: each layer's picked keys move together, its first one `by` after the
previous layer's. The spatial orders compare where each layer is seen, in composition px (placement.centres_at: through
its groups and the camera), so layers in different groups line up as they look.
"""
from __future__ import annotations

import random

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import marked
from rostrum_core.tree import index

from . import fields as F, placement
from .kind import REGISTRY as R
from .ops_timing import _comp_fps, _rebase, _times
from .ops_keytime import _own_seconds
from .retime import offset_of

ORDERS = ["stack", "picked", "left_to_right", "top_to_bottom", "centre", "random"]
WORDS = {"stack": "Stack (top first)", "picked": "As picked", "left_to_right": "Left to right",
         "top_to_bottom": "Top to bottom", "centre": "From the centre", "random": "Random"}


def ranks(items: list[dict], order: str, stack: list[str]) -> list[int]:
    """Each item's place in the cascade (0 first; equal places start together: from the centre, two at the same
    distance). `items` in pick order with their x / y at their start; `stack` the ids top of the list first."""
    n = len(items)
    if order == "picked":
        return list(range(n))
    if order == "stack":
        return [stack.index(it["id"]) for it in items]
    if order == "random":           # the same layers give the same cascade every time (a re-run changes nothing)
        ids = sorted(it["id"] for it in items)
        places = list(range(n))
        random.Random(",".join(ids)).shuffle(places)
        return [places[ids.index(it["id"])] for it in items]
    if order == "centre":
        cx, cy = sum(it["x"] for it in items) / n, sum(it["y"] for it in items) / n
        far = [round(((it["x"] - cx) ** 2 + (it["y"] - cy) ** 2) ** 0.5) for it in items]
        steps = sorted(set(far))
        return [steps.index(d) for d in far]
    axis = "x" if order == "left_to_right" else "y"
    by = sorted(range(n), key=lambda i: (items[i][axis], i))
    return [by.index(i) for i in range(n)]


def _stack(ctx, ids: list[str]) -> list[str]:
    """The ids as the layers list shows them, top first (a parent's later layers are drawn above)."""
    out: list[str] = []

    def walk(node):
        for child in reversed(node.get("layers", [])):
            if child["id"] in ids:
                out.append(child["id"])
            walk(child)
    for comp in ctx.doc.get("comps", []):
        walk(comp)
    return out


@R.operation("layer.stagger", "Make layers start one after another, `by` seconds apart, in an order: stack (top of "
             "the layers list first), picked (the order given), left_to_right, top_to_bottom, centre (from the middle "
             "of the group outwards; equal distances start together) or random (the same every time). Each layer "
             "moves in time with everything in it; the earliest start among them stays.",
             target=F.LAYERS, label="Stagger", importance="secondary", min_targets=2,
             params=[Param.number("by", label="Each starts after", min=0, max=600, step=1 / 30, unit=" s", required=True),
                     Param.choice("order", ORDERS, label="Order", default="stack", labels=WORDS)])
def layer_stagger(ctx, targets, args):
    times = _times(ctx)
    items = []
    for t in targets:
        layer = ctx.item(t)
        if layer.get("locked"):
            ctx.fail(codes.CONFLICT, t, "is locked", hint="Unlock it to move it in time.")
        items.append({"id": t, "start": offset_of(ctx.doc, t, times) + float(layer.get("start", 0.0))})
    for it, delta in _deltas(ctx, items, args):
        _rebase(ctx, ctx.item(it["id"]), delta, _comp_fps(ctx, it["id"]))


def _deltas(ctx, items: list[dict], args: dict):
    """(item, how far it moves) for each item ({id: its layer, start: composition seconds}) in the cascade."""
    by, order = float(args["by"]), args.get("order", "stack")
    if order in ("left_to_right", "top_to_bottom", "centre"):
        when = {it["id"]: max(0.0, offset_of(ctx.doc, it["id"], _times(ctx)) + float(ctx.item(it["id"]).get("start", 0.0)))
                for it in items}
        for it, (x, y) in ((it, placement.centres_at(ctx.doc, when)[it["id"]]) for it in items):
            it["x"], it["y"] = x, y
    base = min(it["start"] for it in items)
    for it, rank in zip(items, ranks(items, order, _stack(ctx, [it["id"] for it in items]))):
        yield it, round(base + rank * by - it["start"], 6)


def _layer_of(ctx, key_id: str) -> str:
    idx = index(ctx.doc, ctx.kind.lists)
    loc = idx[key_id]
    while loc.parent is not None and idx[loc.parent].item["type"] not in F.LAYERS:
        loc = idx[loc.parent]
    return loc.parent


@R.operation("key.stagger", "Make keys on several layers start one after another: each layer's picked keys move "
             "together, so its first one comes `by` seconds after the previous layer's, in an order (as layer.stagger: "
             "stack, picked, left_to_right, top_to_bottom, centre, random). The earliest key stays. Needs keys of two or "
             "more layers.", target="key", label="Stagger keys", importance="secondary", min_targets=2,
             params=[Param.number("by", label="Each starts after", min=0, max=600, step=1 / 30, unit=" s", required=True),
                     Param.choice("order", ORDERS, label="Order", default="stack", labels=WORDS)])
def key_stagger(ctx, targets, args):
    times, groups = _times(ctx), {}
    for kid in targets:
        groups.setdefault(_layer_of(ctx, kid), []).append(kid)
    if len(groups) < 2:
        ctx.fail(codes.BAD_ARGUMENT, "targets", "keys of one layer", "need keys of two or more layers",
                 hint="Pick keys on several layers (or stagger the layers themselves: layer.stagger).")
    items = []
    for layer, kids in groups.items():
        if ctx.item(layer).get("locked"):
            ctx.fail(codes.CONFLICT, layer, "is locked", hint="Unlock it to move its keys.")
        own = {k: _own_seconds(ctx, ctx.item(k), _owner_id(ctx, k)) for k in kids}
        items.append({"id": layer, "keys": own, "start": min(own[k] + offset_of(ctx.doc, _owner_id(ctx, k), times) for k in kids)})
    new = {kid: old + delta for it, delta in _deltas(ctx, items, args) for kid, old in it["keys"].items()}
    for kid, t in new.items():                  # never two keys of one setting at one time (key.scale's rule)
        owner, prop = _owner_id(ctx, kid), ctx.item(kid)["prop"]
        clash = [k["id"] for k in ctx.item(owner).get("keys", []) if k["prop"] == prop and k["id"] != kid
                 and abs(new.get(k["id"], _own_seconds(ctx, k, owner)) - t) < 1e-6]
        if clash:
            ctx.fail(codes.CONFLICT, kid, f"would land on {clash[0]} ({prop}) after staggering",
                     hint="Stagger by another amount, or move that key first.")
    for kid, t in new.items():
        key = ctx.item(kid)
        old = _own_seconds(ctx, key, _owner_id(ctx, kid))
        ctx.set(kid, "t", marked.moved(key["t"], t - old) if marked.marked(key) else round(t, 6))


def _owner_id(ctx, key_id: str) -> str:
    return index(ctx.doc, ctx.kind.lists)[key_id].parent
