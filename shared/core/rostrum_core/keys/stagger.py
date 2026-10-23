"""Cascades (apps/2d UX_SPEC 3.19 Stagger): items put in an order, each starting `by` seconds after the one before,
counting from the earliest start among them; staggering again re-spreads from there. `key.stagger` does it with picked
keys: each group's picked keys (2D: a layer's) move together, its first one `by` after the previous group's.
An app with a stacking order and places on screen passes `Orders` (stack, left_to_right, top_to_bottom, centre);
picked and random need nothing.
"""
from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from ..errors import codes
from ..params import Param
from . import marked

BASIC = ["picked", "random"]
SPATIAL = ["left_to_right", "top_to_bottom", "centre"]
WORDS = {"stack": "Stack (top first)", "picked": "As picked", "left_to_right": "Left to right",
         "top_to_bottom": "Top to bottom", "centre": "From the centre", "random": "Random"}


@dataclass(frozen=True)
class Orders:
    """An app's own orders: `stack(ctx, ids)` -> the ids as its list shows them, top first; `places(ctx, items)` ->
    {id: (x, y)} where each item ({id, start}) is seen at its start."""
    stack: Callable
    places: Callable

    names = ["stack", "picked", "left_to_right", "top_to_bottom", "centre", "random"]


def ranks(items: list[dict], order: str, stack: list[str]) -> list[int]:
    """Each item's place in the cascade (0 first; equal places start together: from the centre, two at the same
    distance). `items` in pick order with their x / y at their start; `stack` the ids top of the list first."""
    n = len(items)
    if order == "picked":
        return list(range(n))
    if order == "stack":
        return [stack.index(it["id"]) for it in items]
    if order == "random":           # the same items give the same cascade every time (a re-run changes nothing)
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


def cascade(ctx, items: list[dict], args: dict, orders: Orders | None):
    """(item, how far it moves) for each item ({id, start: scene seconds}) in the cascade."""
    by, order = float(args["by"]), args.get("order", "stack" if orders else "picked")
    if order in SPATIAL:
        for it, (x, y) in ((it, orders.places(ctx, items)[it["id"]]) for it in items):
            it["x"], it["y"] = x, y
    stack = orders.stack(ctx, [it["id"] for it in items]) if orders and order == "stack" else []
    base = min(it["start"] for it in items)
    for it, rank in zip(items, ranks(items, order, stack)):
        yield it, round(base + rank * by - it["start"], 6)


def order_param(orders: Orders | None) -> Param:
    names = Orders.names if orders else BASIC
    return Param.choice("order", names, label="Order", default=names[0], labels={n: WORDS[n] for n in names})


def register_key_stagger(registry, timing, orders: Orders | None) -> None:
    """key.stagger on `registry` (anim_ops.register_anim_ops calls it)."""
    words = ", ".join(Orders.names if orders else BASIC)

    @registry.operation("key.stagger", "Make keys on several items start one after another: each item's picked keys move "
                        f"together, so its first one comes `by` seconds after the previous item's, in an order ({words}). "
                        "The earliest key stays. Needs keys of two or more items.",
                        target="key", label="Stagger keys", importance="secondary", min_targets=2,
                        params=[Param.number("by", label="Each starts after", min=0, max=600, step=1 / 30, unit=" s", required=True),
                                order_param(orders)])
    def key_stagger(ctx, targets, args):
        from .anim_ops import owner_of
        groups: dict[str, list[str]] = {}
        for kid in targets:
            groups.setdefault(timing.group_of(ctx, kid), []).append(kid)
        if len(groups) < 2:
            ctx.fail(codes.BAD_ARGUMENT, "targets", "keys of one item", "need keys of two or more items",
                     hint="Pick keys on several items (or stagger the items themselves).")
        own_of = {kid: owner_of(ctx, kid)["id"] for kid in targets}
        items = []
        for group, kids in groups.items():
            if ctx.item(group).get("locked"):
                ctx.fail(codes.CONFLICT, group, "is locked", hint="Unlock it to move its keys.")
            own = {k: timing.own_seconds(ctx, ctx.item(k), own_of[k]) for k in kids}
            items.append({"id": group, "keys": own, "start": min(own[k] + timing.offset(ctx, own_of[k]) for k in kids)})
        new = {kid: old + delta for it, delta in cascade(ctx, items, args, orders) for kid, old in it["keys"].items()}
        for kid, t in new.items():                  # never two keys of one setting at one time (key.scale's rule)
            owner, prop = own_of[kid], ctx.item(kid)["prop"]
            clash = [k["id"] for k in ctx.item(owner).get("keys", []) if k["prop"] == prop and k["id"] != kid
                     and abs(new.get(k["id"], timing.own_seconds(ctx, k, owner)) - t) < 1e-6]
            if clash:
                ctx.fail(codes.CONFLICT, kid, f"would land on {clash[0]} ({prop}) after staggering",
                         hint="Stagger by another amount, or move that key first.")
        for kid, t in new.items():
            key = ctx.item(kid)
            old = timing.own_seconds(ctx, key, own_of[kid])
            ctx.set(kid, "t", marked.moved(key["t"], t - old) if marked.marked(key) else round(t, 6))
