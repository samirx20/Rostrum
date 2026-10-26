"""layer.stagger: layers start one after another (UX_SPEC 3.19 Stagger). The layers are put in an order, then each
moves in time (with its keys, effects, drawings: layer.shift's way) so it starts `by` seconds after the one before,
counting from the earliest start among them. Staggering again re-spreads from there, so it can be changed at will.
key.stagger (rostrum_core.keys.stagger, registered in ops_anim.py) does the same with picked keys, through this file's
CASCADE. The spatial orders compare where each layer is seen, in composition px (placement.centres_at: through
its groups and the camera), so layers in different groups line up as they look; a layer that enters unseen (from
opacity or scale 0) counts where it sits (its own scale and opacity taken as full), in one engine ask for all.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys.stagger import WORDS as CORE_WORDS, Orders, cascade, order_param, ranks  # noqa: F401  (ranks: tests)

from . import fields as F, placement
from .kind import REGISTRY as R
from .ops_timing import _comp_fps, _rebase, _times
from .retime import offset_of

CASCADE = Orders(stack=lambda ctx, ids: _stack(ctx, ids), places=lambda ctx, items: _places(ctx, items))   # key.stagger's too (ops_anim.py)
ORDERS = Orders.names                  # the order names (the screen's Stagger list)
WORDS = {n: CORE_WORDS[n] for n in ORDERS}


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
             target=F.PLACED, label="Stagger", importance="secondary", min_targets=2,
             params=[Param.number("by", label="Each starts after", min=0, max=600, step=1 / 30, unit=" s", required=True),
                     order_param(CASCADE)])
def layer_stagger(ctx, targets, args):
    times = _times(ctx)
    items = []
    for t in targets:
        layer = ctx.item(t)
        if layer.get("locked"):
            ctx.fail(codes.CONFLICT, t, "is locked", hint="Unlock it to move it in time.")
        items.append({"id": t, "start": offset_of(ctx.doc, t, times) + float(layer.get("start", 0.0))})
    for it, delta in cascade(ctx, items, args, CASCADE):
        _rebase(ctx, ctx.item(it["id"]), delta, _comp_fps(ctx, it["id"]))


def _places(ctx, items: list[dict]) -> dict:
    """Where each layer is seen at its start ({id: (x, y)}, composition px through its groups and the camera)."""
    when = {it["id"]: max(0.0, offset_of(ctx.doc, it["id"], _times(ctx)) + float(ctx.item(it["id"]).get("start", 0.0)))
            for it in items}
    try:
        return placement.centres_at(ctx.doc, when)
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, "order", str(e))
