"""Layer switches: lock (the screen won't pick or drag it, and every operation refuses it until it is unlocked) and hide
(not drawn, in the preview and in an export: scene.py leaves a hidden layer out). Both are plain fields (`locked`,
`hidden`; fields.py STATE), these are the one-step ways to change several at once."""
from __future__ import annotations

from rostrum_core import PLUGIN_ITEM, Param

from . import fields as F
from .kind import REGISTRY as R

LAYERS = (*F.PLACED, PLUGIN_ITEM)          # hide: never the frame (it is what is exported); lock: the frame too (its Locked switch)


@R.operation("layer.lock", "Lock layers: they can't be picked or dragged on the screen and operations refuse them until "
             "layer.unlock.", target=(*F.LAYERS, PLUGIN_ITEM), label="Lock", importance="secondary")
def layer_lock(ctx, targets, args):
    for t in targets:
        ctx.set(t, "locked", True)


@R.operation("layer.unlock", "Unlock layers.", target=(*F.LAYERS, PLUGIN_ITEM), label="Unlock", importance="secondary")
def layer_unlock(ctx, targets, args):
    for t in targets:
        ctx.set(t, "locked", False)


@R.operation("layer.hide", "Hide layers (on, the default) or show them again (on false): a hidden layer is not drawn, in the "
             "preview or in an export, and still keeps everything it has.", target=LAYERS, label="Hide", importance="secondary",
             params=[Param.toggle("on", label="Hidden", default=True)])
def layer_hide(ctx, targets, args):
    for t in targets:
        ctx.set(t, "hidden", args.get("on", True))
