"""`layer.anchor`: move the point a layer turns and scales around, in one step (CANVAS.md §2 row 4). The anchor is a
fraction of the layer's own box, 0..1 across (`x`) and down (`y`); 0.5, 0.5 is the middle (past 0 or 1: outside the
box). `keep_place` (the default) moves Position with it so the layer stays exactly where it shows (After Effects'
"pan behind"); off, the layer moves so its new anchor sits where the old one was. A layer an auto layout places keeps
no Position of its own: only the anchor changes. The canvas's anchor ring drags with this same op
(screen2d/anchor_slots.py), so hand and agent are the same. Fields are written the way `value.set` does it: a still field changes, an animated one gets a key at `at`;
a key timed on a shared marker at `at` (within half a frame) is that key: it changes and stays on its marker."""
from __future__ import annotations

import copy
import math

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import marked
from rostrum_core.tree import index

from . import ops_timing
from .evaluate import resolve
from .retime import offset_of
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


def _placed(ctx, item: dict) -> dict:
    """The item with its keys timed on a marker placed (in its own seconds, the written time kept in `ref`), so its
    values can be read; the item itself when it has none."""
    if not any(marked.marked(k) for k in item.get("keys", [])):
        return item
    times = ops_timing._times(ctx)
    placed = copy.deepcopy(item)
    marked.resolve(placed, times, offset_of(ctx.doc, item["id"], times))
    return placed


def _write(ctx, placed: dict, prop: str, value: float, args: dict, fps: float) -> None:
    """As value.set (ops_align._put), except that a key of the field timed on a marker within half a frame of `at`
    is THE key there: it changes and stays on its marker (key.add at its written time), never a plain key beside it."""
    if "at" in args:
        on = next((k for k in placed.get("keys", []) if k["prop"] == prop and "ref" in k
                   and abs(k["t"] - args["at"]) < 0.5 / fps), None)
        if on is not None:
            R.get("key.add").fn(ctx, [placed["id"]], {"prop": prop, "t": on["ref"], "v": round(value, 4)})
            return
    _put(ctx, placed["id"], prop, value, args)


@R.operation("layer.anchor", "Move the anchor point (what a layer turns and scales around) to `x`, `y`: fractions of its "
             "own box, 0 = left / top, 0.5 = the middle, 1 = right / bottom (either may be left out: it stays). "
             "`keep_place` (default true): Position moves too so the layer stays exactly where it shows; false: the "
             "layer moves so the new anchor lands where the old one was. Writes anchorX, anchorY (and x, y); a key of "
             "theirs timed on a shared marker at `at` is changed on its marker.",
             target=PLACED, label="Anchor", importance="secondary",
             params=[Param.number("x", label="Across", help="0 left … 1 right (outside the box below 0 or past 1)", **_FRACTION),
                     Param.number("y", label="Down", help="0 top … 1 bottom", **_FRACTION),
                     Param.toggle("keep_place", label="Keep its place", default=True), AT])
def layer_anchor(ctx, targets, args):
    if "x" not in args and "y" not in args:
        ctx.fail(codes.BAD_ARGUMENT, "x, y", "are both missing", hint="Give the anchor's new x and / or y (0..1).")
    t, idx = args.get("at", 0.0), index(ctx.doc, ctx.kind.lists)
    for i in targets:
        item = _placed(ctx, ctx.item(i))
        p = resolve(item, t)
        ax, ay = float(args.get("x", p["anchorX"])), float(args.get("y", p["anchorY"]))
        laid_out = has_layout(ctx.item(idx[i].parent))
        fps = ops_timing._comp_fps(ctx, i, idx)
        if args.get("keep_place", True) and not laid_out:
            dx, dy = moved(p, own_size(item["type"], p), ax, ay)
            for prop, d in (("x", dx), ("y", dy)):
                if abs(d) > 1e-9:
                    _write(ctx, item, prop, p[prop] + d, args, fps)
        for prop, v in (("anchorX", ax), ("anchorY", ay)):
            if abs(v - p[prop]) > 1e-12:
                _write(ctx, item, prop, v, args, fps)
