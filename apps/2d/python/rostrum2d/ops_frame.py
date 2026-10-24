"""Frame operations: `comp.size` (a named frame size) and `layer.fill_frame` (a layer scaled to cover, or to sit inside,
its parent's frame). Positions and scale change the way `value.set` does it: a still field changes, an animated one
gets a key at `at`. Each call is one change = one undo step."""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes

from . import frame_sizes
from .evaluate import resolve
from .kind import REGISTRY as R
from .ops_align import AT, SIZED, _frame, _parent, _put
from .sizes import own_size


@R.operation("comp.size", "Give the scene one of the named frame sizes (Wide 16:9, 4K 16:9, Vertical 9:16, Square 1:1, "
             "Post 4:5). Layers stay where they are; other sizes: comp.set width / height.", target="comp", label="Size",
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
        need_u, need_v = (c * W + s * H) / 2, (s * W + c * H) / 2
        return max(need_u / (w / 2), need_v / (h / 2))
    return min(W / (c * w + s * h), H / (s * w + c * h))


@R.operation("layer.fill_frame", "Scale layers so they cover the whole frame of their parent (mode cover, the default: no "
             "edge left showing, the overflow is cropped) or sit entirely inside it (mode inside), centred. Keeps the "
             "layer's turn and stretch; a text has no size of its own and is refused.", target=SIZED, label="Fill the frame",
             params=[Param.choice("mode", ["cover", "inside"], label="How", default="cover",
                                  labels={"cover": "Fill the frame", "inside": "Fit inside"}), AT])
def layer_fill_frame(ctx, targets, args):
    parent, t = _parent(ctx, targets), args.get("at", 0.0)
    _, _, W, H = _frame(parent, t)
    for i in targets:
        p = resolve(ctx.item(i), t)
        w, h = own_size(ctx.item(i)["type"], p)
        sx, sy = w * p["scaleX"], h * p["scaleY"]
        if sx <= 0 or sy <= 0:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{i}"', "has no size to scale")
        k = _scale_for(args.get("mode", "cover"), sx, sy, p["rotation"], W, H)
        r = math.radians(p["rotation"])        # the box's centre sits at the frame's centre: move the anchor to match
        dx, dy = (0.5 - p["anchorX"]) * sx * k, (0.5 - p["anchorY"]) * sy * k
        _put(ctx, i, "scale", k, args)
        _put(ctx, i, "x", W / 2 - (math.cos(r) * dx - math.sin(r) * dy), args)
        _put(ctx, i, "y", H / 2 - (math.sin(r) * dx + math.cos(r) * dy), args)
