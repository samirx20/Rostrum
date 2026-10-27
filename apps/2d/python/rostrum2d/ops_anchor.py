"""`layer.anchor`: move the point a layer turns and scales around, in one step (CANVAS.md §2 row 4). The anchor is a
fraction of the layer's own box, 0..1 across (`x`) and down (`y`); 0.5, 0.5 is the middle (past 0 or 1: outside the
box). `keep_place` (the default) moves Position with it so the layer stays exactly where it shows (After Effects'
"pan behind"); off, the layer moves so its new anchor sits where the old one was. A layer an auto layout places keeps
no Position of its own: only the anchor changes. The canvas's anchor ring drags with this same op
(screen2d/anchor_slots.py), so hand and agent are the same. Fields are written the way `value.set` does it: a still field changes, an animated one gets a key at `at`."""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from .evaluate import resolve
from .kind import REGISTRY as R
from .layout import has_layout
from .ops_align import AT, PLACED, _put
from .sizes import own_size

_FRACTION = dict(min=-10, max=10, importance="primary")    # the Anchor fields' own range: it may sit outside the box


def moved(p: dict, size: tuple[float, float], ax: float, ay: float) -> tuple[float, float]:
    """How far Position moves (parent px) to keep a layer with values `p` and own size `size` in place while its anchor
    goes to (ax, ay): the anchor's step along the layer's own sides (Stretch and Scale, a negative Stretch running the
    other way), turned with it."""
    sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
    vx, vy = (ax - p["anchorX"]) * size[0] * sx, (ay - p["anchorY"]) * size[1] * sy
    c, s = math.cos(math.radians(p["rotation"])), math.sin(math.radians(p["rotation"]))
    return c * vx - s * vy, s * vx + c * vy


@R.operation("layer.anchor", "Move the anchor point (what a layer turns and scales around) to `x`, `y`: fractions of its "
             "own box, 0 = left / top, 0.5 = the middle, 1 = right / bottom (either may be left out: it stays). "
             "`keep_place` (default true): Position moves too so the layer stays exactly where it shows; false: the "
             "layer moves so the new anchor lands where the old one was. Writes anchorX, anchorY (and x, y).",
             target=PLACED, label="Anchor", importance="secondary",
             params=[Param.number("x", label="Across", help="0 left … 1 right (outside the box below 0 or past 1)", **_FRACTION),
                     Param.number("y", label="Down", help="0 top … 1 bottom", **_FRACTION),
                     Param.toggle("keep_place", label="Keep its place", default=True), AT])
def layer_anchor(ctx, targets, args):
    if "x" not in args and "y" not in args:
        ctx.fail(codes.BAD_ARGUMENT, "x, y", "are both missing", hint="Give the anchor's new x and / or y (0..1).")
    t, idx = args.get("at", 0.0), index(ctx.doc, ctx.kind.lists)
    for i in targets:
        item = ctx.item(i)
        p = resolve(item, t)
        ax, ay = float(args.get("x", p["anchorX"])), float(args.get("y", p["anchorY"]))
        laid_out = has_layout(ctx.item(idx[i].parent))
        if args.get("keep_place", True) and not laid_out:
            dx, dy = moved(p, own_size(item["type"], p), ax, ay)
            for prop, d in (("x", dx), ("y", dy)):
                if abs(d) > 1e-9:
                    _put(ctx, i, prop, p[prop] + d, args)
        for prop, v in (("anchorX", ax), ("anchorY", ay)):
            if abs(v - p[prop]) > 1e-12:
                _put(ctx, i, prop, v, args)
