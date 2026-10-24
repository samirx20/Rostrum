"""Frame operations: `comp.size` (a named frame size) and `layer.fill_frame` (a layer scaled to cover, or to sit inside,
its parent's frame). Positions and scale change the way `value.set` does it: a still field changes, an animated one
gets a key at `at`. Each call is one change = one undo step."""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes

from . import cover, frame_sizes
from .evaluate import resolve
from .kind import REGISTRY as R
from .ops_align import AT, SIZED, _frame, _parent, _put
from .sizes import own_size


@R.operation("comp.size", "Give the scene one of the named frame sizes (Wide 16:9, 4K 16:9, Vertical 9:16, Square 1:1, "
             "Post 4:5). The frame takes the new size about its centre (it keeps looking at the same point; its zoom, turn, "
             "keys and home stay); layers in the world stay where they are; pinned layers keep their distance from the "
             "frame's centre, so a centred title stays centred. Other sizes: comp.set width / height (the same rule).",
             target="comp", label="Size",
             params=[Param.choice("size", frame_sizes.IDS, label="Size", required=True,
                                  labels={s[0]: frame_sizes.label(s) for s in frame_sizes.SIZES})])
def comp_size(ctx, targets, args):
    _, _, w, h = frame_sizes.get(args["size"])
    from .frame import make
    for t in targets:
        item = ctx.item(t)
        size = (item.get("width", 0.0), item.get("height", 0.0))
        ctx.set(t, "width", w)
        ctx.set(t, "height", h)
        make.resized(ctx, t, size)


def _scale_for(mode: str, w: float, h: float, r: float, W: float, H: float) -> float:
    """The scale that makes a w × h box turned by r degrees cover the W × H frame (cover) or sit inside it (inside),
    both centred on the same point."""
    c, s = abs(math.cos(math.radians(r))), abs(math.sin(math.radians(r)))
    if mode == "cover":     # every frame corner, taken into the box's own turn, must lie within its half sides
        return cover.scale_to_cover((c * W + s * H) / 2, (s * W + c * H) / 2, w, h)
    return min(W / (c * w + s * h), H / (s * w + c * h))


@R.operation("layer.fill_frame", "Scale layers so they cover the whole frame of their parent (mode cover, the default: no "
             "edge left showing, the overflow is cropped) or sit entirely inside it (mode inside), centred. Keeps the "
             "layer's turn and stretch; a text has no size of its own and is refused.", target=SIZED, label="Fill the frame",
             params=[Param.choice("mode", ["cover", "inside"], label="How", default="cover",
                                  labels={"cover": "Fill the frame", "inside": "Fit inside"}), AT])
def layer_fill_frame(ctx, targets, args):
    parent, t = _parent(ctx, targets), args.get("at", 0.0)
    for i in targets:
        x0, y0, x1, y1 = _frame(parent, t, bool(ctx.item(i).get("screenLock")))     # the frame where it is at t
        W, H = x1 - x0, y1 - y0
        p = resolve(ctx.item(i), t)
        w, h = own_size(ctx.item(i)["type"], p)
        sx, sy = w * p["scaleX"], h * p["scaleY"]
        if sx <= 0 or sy <= 0:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{i}"', "has no size to scale")
        k = _scale_for(args.get("mode", "cover"), sx, sy, p["rotation"], W, H)
        x, y = cover.anchor_at(x0 + W / 2, y0 + H / 2, sx * k, sy * k, p["anchorX"], p["anchorY"], p["rotation"])
        _put(ctx, i, "scale", k, args)
        _put(ctx, i, "x", x, args)
        _put(ctx, i, "y", y, args)
