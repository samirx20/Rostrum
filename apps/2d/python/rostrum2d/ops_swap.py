"""Swap set operations (swap.py): `swap.show` puts one choice key on a slot; `blink.add` keys blinks across a stretch.
Both only write hold keys on the set's `show` field, so a person edits them like any other key on the timeline."""
from __future__ import annotations

import random

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import key_id
from rostrum_core.tree import index

from .kind import REGISTRY as R
from .lipsync.ops import comp_of
from .ops_keys import put_key
from .swap import child_index

SECONDS = dict(min=0, max=36000, unit="s")


def _slot(ctx, id_) -> list[str]:
    """The ids of a swap set's children; fails loudly if it isn't a swap set."""
    item = ctx.item(id_)
    if not item.get("swap"):
        ctx.fail(codes.BAD_ARGUMENT, id_, "is not a swap set", hint="Turn on its `swap` (One at a time) first.")
    return [c["id"] for c in item.get("layers", [])]


def _which(ctx, kids, which, name) -> int:
    try:
        return child_index(kids, which)
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, name, str(e), kids)


def _add(ctx, slot, plan: dict[float, int]) -> int:
    """Hold keys on `show`; a time that already has one (or a key of that id) is left as it is. Returns how many."""
    known, n = index(ctx.doc, ctx.kind.lists), 0
    there = {round(k["t"], 4) for k in ctx.item(slot).get("keys", []) if k["prop"] == "show"}
    for at, i in sorted(plan.items()):
        if key_id(slot, "show", at) not in known and round(at, 4) not in there:
            put_key(ctx, slot, "show", at, {"v": i, "ease": "hold"})
            n += 1
    return n


@R.operation("swap.show", "Make a swap set show one of its children from a time on (a hold key on `show`: a jump, "
             "never a blend). Name the child by its id, or count from 0.", target="group", label="Swap drawing",
             params=[Param.number("t", label="At", required=True, **SECONDS),
                     Param.id("layer", kind="layer", label="Shows", help="A child of the swap set"),
                     Param.number("index", label="Or its place", min=0, max=999, integer=True,
                                  help="0 = the first child; used when no child is named")])
def swap_show(ctx, targets, args):
    if "layer" not in args and "index" not in args:
        ctx.fail(codes.BAD_ARGUMENT, "layer", "is required", hint="Give `layer` (a child id) or `index` (from 0).")
    for t in targets:
        kids = _slot(ctx, t)
        i = _which(ctx, kids, args["layer"] if "layer" in args else int(args["index"]), "layer")
        put_key(ctx, t, "show", args["t"], {"v": i, "ease": "hold"})


def blinks(start: float, end: float, every: float, vary: float, seed: int) -> list[float]:
    """The times of the blinks: about `every` seconds apart, each gap off by up to `vary` (0..1) of it, the same for a seed."""
    rng, t, out = random.Random(seed), start, []
    while True:
        t += every * (1 + vary * rng.uniform(-1, 1))
        if t > end:
            return out
        out.append(round(t, 4))


@R.operation("blink.add", "Key blinks on a swap set: the open eyes show, now and then the closed drawing for a few "
             "frames (with `half`, a half-closed drawing one frame before and after). Adds keys only; keys already "
             "there stay. The same seed gives the same blinks.", target="group", label="Blinks",
             params=[Param.id("open", kind="layer", label="Eyes open", required=True),
                     Param.id("closed", kind="layer", label="Eyes closed", required=True),
                     Param.id("half", kind="layer", label="Half closed", help="Shown a frame either side of closed"),
                     Param.number("start", label="From", default=0.0, **SECONDS),
                     Param.number("end", label="To", help="Default: the end of the composition", **SECONDS),
                     Param.number("every", label="Every", default=3.5, min=0.1, max=60, unit="s",
                                  help="Mean time between blinks"),
                     Param.number("vary", label="Varies by", default=0.3, min=0, max=1, step=0.05,
                                  help="0 = evenly spaced; 1 = a gap can be anything from none to twice the mean"),
                     Param.number("seed", label="Seed", default=0, integer=True, min=0, max=999999,
                                  importance="secondary", help="Another seed, other blink times"),
                     Param.number("frames", label="Closed for", default=2, min=1, max=30, integer=True, unit="frames",
                                  importance="secondary")])
def blink_add(ctx, targets, args):
    for t in targets:
        kids = _slot(ctx, t)
        o, c = (_which(ctx, kids, args[n], n) for n in ("open", "closed"))
        h = _which(ctx, kids, args["half"], "half") if args.get("half") else None
        comp = comp_of(ctx, t)
        dt, n = 1 / comp.get("fps", 30), args.get("frames", 2)
        start, end = args.get("start", 0.0), args.get("end", comp.get("duration", 0.0))
        plan = {round(start, 4): o}
        for b in blinks(start, end, args.get("every", 3.5), args.get("vary", 0.3), args.get("seed", 0)):
            if h is not None:
                plan[round(b - dt, 4)] = h
            plan[b] = c
            if h is not None:
                plan[round(b + n * dt, 4)] = h
            plan[round(b + (n + (h is not None)) * dt, 4)] = o
        _add(ctx, t, plan)
