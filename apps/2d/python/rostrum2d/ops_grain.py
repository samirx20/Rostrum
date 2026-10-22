"""`grain.add`: film grain over the whole picture, made from what exists: a looping video layer of real noise on top of
the scene, screen-locked, blended Overlay. Its `src` is the grain's recipe (grain.py), so the clip is made from it
wherever the layer is drawn. Amount is its opacity and size its scale, both ordinary settings of that layer afterwards (keyable). Same inputs, same grain."""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes

from . import grain
from .kind import REGISTRY as R
from .ops_items import new_item


@R.operation("grain.add", "Add film grain over the whole picture: a screen-locked, looping layer of moving noise on top "
             "of the composition's layers, blended Overlay. `amount` is how strong (its opacity), `size` how coarse a grain "
             "is in px. Afterwards its Opacity and Scale are the amount and size, and can be keyed.", target="comp",
             label="Add grain",
             params=[Param.number("amount", label="Amount", min=0, max=1, step=0.01, default=0.3),
                     Param.number("size", label="Grain size", min=1, max=16, step=0.5, unit="px", default=2.0),
                     Param.number("seed", label="Seed", min=0, max=100000, integer=True, default=1, importance="deep",
                                  help="A different seed is a different, equally random grain")])
def grain_add(ctx, targets, args):
    for t in targets:
        comp = ctx.item(t)
        size = float(args.get("size", 2.0))
        w, h = math.ceil(comp["width"] / size), math.ceil(comp["height"] / size)
        if w < 2 or h < 2:
            ctx.fail(codes.BAD_ARGUMENT, f"size={size}", "is bigger than the frame")
        src = grain.src_of(w, h, float(comp["fps"]), int(args.get("seed", 1)))   # the recipe, not a path (grain.py)
        item = new_item(ctx, "video", {"name": "Grain"}, src=src, w=w, h=h, fit="stretch", loop=True, scale=size,
                        x=comp["width"] / 2, y=comp["height"] / 2, blend="overlay", opacity=float(args.get("amount", 0.3)),
                        screenLock=True, locked=False)
        ctx.insert(t, "layers", item)
