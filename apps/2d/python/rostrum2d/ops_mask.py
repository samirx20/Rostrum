"""Select first, then act: `mask.make` ("Mask with this layer") and `mask.release`. The cutter and the layers it cuts go
into one new group (as group.make) and each cut layer's track matte (fields.py `matte`, `matteMode`) is the cutter; the
engine draws a matte layer only as the matte. Not to be confused with `mask.add`: that adds a mask *shape* to a layer."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import fields as F
from .kind import REGISTRY as R
from .ops_group import AT, make_group
from .ops_items import ID


@R.operation("mask.make", "Mask with a layer: select the layers to cut (target), name the layer that cuts them (`cutter`, "
             "a sibling). They all go into one new group and each cut layer shows only where the cutter is drawn "
             "(`mode`: its shape, outside its shape, its brightness or its darkness); the cutter itself is not drawn. "
             "Every layer keeps its place on screen and in time. mask.release undoes the link.",
             target=F.LAYERS, label="Mask with this layer",
             params=[Param.id("cutter", kind="layer", label="Cutting layer", required=True),
                     Param.choice("mode", F.MATTE_MODES, label="Cut by", default="alpha",
                                  labels={"alpha": "Its shape", "alphaInverted": "Outside its shape", "luma": "Its brightness",
                                          "lumaInverted": "Its darkness"}), ID, AT])
def mask_make(ctx, targets, args):
    cutter, idx = args["cutter"], index(ctx.doc, ctx.kind.lists)
    if cutter in targets:
        ctx.fail(codes.BAD_ARGUMENT, f'cutter "{cutter}"', "is also one of the layers to cut")
    if cutter not in idx or idx[cutter].item["type"] not in F.LAYERS:
        ctx.fail(codes.NOT_FOUND, f'cutter "{cutter}"', "is not a layer")
    for t in (cutter, *targets):
        if F.param(ctx.item(t)["type"], "matte") is None:
            ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', f"is a {ctx.item(t)['type']}, which can't be masked or cut")
    make_group(ctx, [cutter, *targets], "group", "Group", args)
    for t in targets:
        ctx.set(t, "matte", cutter)
        ctx.set(t, "matteMode", args.get("mode", "alpha"))


@R.operation("mask.release", "Unlink a mask: the selected layers (cut layers, or the cutting layer) stop being cut and "
             "the cutter is drawn again. The group stays a plain group.", target=F.LAYERS, label="Release mask",
             importance="secondary")
def mask_release(ctx, targets, args):
    idx = index(ctx.doc, ctx.kind.lists)
    cut = {t for t in targets if ctx.item(t).get("matte")}
    cut |= {i for i, l in idx.items() if l.item.get("matte") in targets}
    if not cut:
        ctx.fail(codes.BAD_ARGUMENT, f"target {targets}", "are not cut by a mask and not cutting anything")
    for t in sorted(cut):
        ctx.set(t, "matte", "")
