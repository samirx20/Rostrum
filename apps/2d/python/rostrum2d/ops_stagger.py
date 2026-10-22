"""layer.stagger: layers start one after another (UX_SPEC 3.19 Stagger). The layers are put in an order, then each
moves in time (with its keys, effects, drawings: layer.shift's way) so it starts `by` seconds after the one before,
counting from the earliest start among them. Staggering again re-spreads from there, so it can be changed at will.
"""
from __future__ import annotations

import random

from rostrum_core import Param
from rostrum_core.errors import codes

from . import fields as F
from .evaluate import resolve
from .kind import REGISTRY as R
from .ops_timing import _comp_fps, _rebase, _times
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
    by, order = float(args["by"]), args.get("order", "stack")
    times = _times(ctx)
    items = []
    for t in targets:
        layer = ctx.item(t)
        if layer.get("locked"):
            ctx.fail(codes.CONFLICT, t, "is locked", hint="Unlock it to move it in time.")
        own = float(layer.get("start", 0.0))
        p = resolve(layer, own)
        items.append({"id": t, "x": p.get("x", 0.0), "y": p.get("y", 0.0), "start": offset_of(ctx.doc, t, times) + own})
    base = min(it["start"] for it in items)
    for it, rank in zip(items, ranks(items, order, _stack(ctx, targets))):
        delta = round(base + rank * by - it["start"], 6)
        _rebase(ctx, ctx.item(it["id"]), delta, _comp_fps(ctx, it["id"]))
