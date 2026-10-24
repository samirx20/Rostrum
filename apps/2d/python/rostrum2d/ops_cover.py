"""Cover the frame's move (`background.fit`): a scene's own sized layer made to cover everything the frame shows of it
at its depth over the whole piece. A drawing's canvas grows (paint_grow.py, as painting past its edge does);
any other sized layer is scaled evenly and placed with the cover maths `layer.fill_frame` uses (cover.py). One call is
one change = one undo step."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import keys_of

from . import background as B, cover, paint_grow
from .boxes import matrix
from .evaluate import resolve
from .frame import place, view
from .kind import REGISTRY as R
from .ops_align import SIZED, _put
from .ops_background import _comp_of
from .sizes import own_size

FIT_WHEN = {"all": [{"fact": "underCamera"}, {"fact": "frameMoves"}, {"not": {"is": ["screenLock", True]}}]}
STILL = (*place.FIELDS, "depth")        # what Cover the frame's move sets or reads once: keyed, it would be wrong at other times


def applies(layer: dict, comp: dict) -> bool:
    """Whether Cover the frame's move can run on a scene's own layer: sized, not pinned, still, not riding, and the
    frame moves (the screen's ⋯ entry and Set depth read this; the operation refuses the same, loudly)."""
    return (layer["type"] in SIZED and not layer.get("screenLock") and not layer.get("ridePath")
            and not _keyed(layer) and view.moves(view.of(comp)))


def _keyed(layer: dict) -> list[str]:
    return [f for f in STILL if keys_of(layer, f)]


@R.operation("background.fit", "Cover the frame's move: size and place layers so they cover everything the frame shows "
             "of them at their depth over the whole piece, with a bleed (run it again after the move changes). A drawing's "
             "canvas grows to it (strokes keep their place in the scene; nothing painted is cut off); any other sized "
             "layer (a picture, shape, group …) is scaled evenly and moved, keeping its turn and stretch. Needs a frame "
             "that moves (keys or a ride); a text has no size of its own; a pinned layer moves with the frame: use "
             "layer.fill_frame for it.", target=SIZED, label="Cover the frame's move", importance="secondary",
             valid_when=FIT_WHEN,
             params=[Param.number("bleed", label="Bleed", min=0, max=2000, unit="px", default=B.BLEED, importance="deep")])
def background_fit(ctx, targets, args):
    bleed = args.get("bleed", B.BLEED)
    for t in targets:
        layer, comp = ctx.item(t), _comp_of(ctx, t)
        place.check(ctx, layer)
        moving = _keyed(layer)
        if moving:
            ctx.fail(codes.CONFLICT, f'{t}.{moving[0]}', "is animated: Cover the frame's move places a layer that stays still",
                     hint="Remove its keys first, or size it by hand.")
        shots = B.shots(comp)
        (_grow if layer["type"] == "drawing" else _cover)(ctx, layer, comp, bleed, shots)


def _cover(ctx, layer, comp, bleed, shots):
    """Any sized layer but a drawing: scaled evenly and moved so its turned box covers the frame's whole move."""
    p = resolve(layer, 0.0)
    w, h = own_size(layer["type"], p)
    if w * p["scaleX"] <= 0 or h * p["scaleY"] <= 0:
        ctx.fail(codes.BAD_ARGUMENT, f'"{layer["id"]}"', "has no size to scale")
    k, x, y = cover.fit(comp, p, w, h, shots, bleed)
    for prop, v in (("scale", k), ("x", x), ("y", y)):
        _put(ctx, layer["id"], prop, v, {})


def _grow(ctx, layer, comp, bleed, shots):
    """A drawing: its canvas grows (paint_grow.grow, the one way a drawing grows: nothing painted moves on screen, its
    place, scale and turn kept) to take in everything the frame shows of it, never shrinks (paint is never cut off);
    nothing changes when it covers already, so its picture isn't made again."""
    p = resolve(layer, 0.0)
    w, h = own_size("drawing", p)
    k = p["scale"] * min(p["scaleX"], p["scaleY"])
    m = matrix(p, w, h)
    own = [view.undo(m, x, y) for shot in shots for x, y in cover.seen(comp, shot, p["depth"])]
    b = bleed / k
    box = (min(u for u, _ in own) - b, min(v for _, v in own) - b, max(u for u, _ in own) + b, max(v for _, v in own) + b)
    if not paint_grow.fits(int(w), int(h), box):
        left, top, right, bottom = paint_grow.need(int(w), int(h), box)
        ctx.fail(codes.BAD_ARGUMENT, f'"{layer["id"]}"', f"would need a {int(w + left + right)}×{int(h + top + bottom)} canvas; "
                 f"a drawing is at most {paint_grow.MOST} px a side",
                 hint="Use a larger depth for it (it moves less), a shorter frame move, or split it into two drawing layers.")
    paint_grow.grow(ctx, layer["id"], box)
