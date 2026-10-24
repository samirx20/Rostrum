"""Pin to frame and Set depth (FRAME.md › Pinned and depth): `layer.pin` and `layer.set_depth` on a scene's own
layers. With keep "shown" (the default) the layer stays exactly where it shows in the export at `at` (the playhead):
its x, y, scale and rotation are carried through the frame's maths there (frame/place.py, view.py), on the still
values and every key, so an animated layer keeps its motion. Keep "values" changes only the switch or the depth.
Each call is one change = one undo step; a layer already as asked is left alone (no empty step)."""
from __future__ import annotations

from rostrum_core import Param

from . import fields as F, retime
from .evaluate import value_at
from .frame import place, view
from .kind import REGISTRY as R
from .ops_frame_fit import _scene, _seconds
from .ops_timing import _times

TOP = {"all": [{"fact": "underCamera"}, {"not": {"is": ["locked", True]}}]}     # a scene's own layer, not locked
KEEP = Param.choice("keep", ["shown", "values"], label="Keep", default="shown",
                    labels={"shown": "Where it shows", "values": "Its numbers"},
                    help='"shown": the layer stays where it shows in the export at `at` (its position, size and turn '
                         'are changed to match, keys included); "values": only the setting changes, so it may jump')
AT = Param.number("at", label="At", min=0, max=36000, unit=" s", markers=True, default=0.0,
                  help="The moment (composition seconds or a marker, the playhead) at which it keeps where it shows")


def _now(ctx, lid: str, at):
    """(the scene with markers placed, the frame at `at`, the layer's depth at `at`, `at` in seconds)."""
    t = _seconds(ctx, at)
    timed = _scene(ctx, lid)[1]
    layer = next(l for l in timed["layers"] if l["id"] == lid)
    return timed, view.shot(timed, t), float(value_at(layer, "depth", t)), t


@R.operation("layer.pin", "Pin layers to the frame (on: they move with the frame, not the world: a title, a logo bug) "
             "or unpin them (off). keep \"shown\" (the default): each stays exactly where it shows in the export at `at`; "
             "its x, y become the frame's own px when pinned (world px when not), its scale and turn take the frame's "
             "zoom and turn, every key included. keep \"values\": only the switch flips. Only a scene's own layers.",
             target=F.PLACED, label="Pin to frame", importance="secondary", valid_when=TOP,
             params=[Param.toggle("on", label="Pinned", required=True), KEEP, AT])
def layer_pin(ctx, targets, args):
    on = bool(args["on"])
    for lid in targets:
        if bool(ctx.item(lid).get("screenLock")) == on:
            continue
        if args.get("keep", "shown") == "shown":
            timed, cam, depth, _ = _now(ctx, lid, args.get("at", 0.0))
            m = view.layer_matrix(timed, cam, {"depth": depth})     # world px -> the frame's own px
            place.carry(ctx, lid, m if on else place.inverse(m))
        ctx.set(lid, "screenLock", on)


@R.operation("layer.set_depth", "Set how far behind the frame's plane layers sit (depth: 0 = on it, 1 = twice as far, "
             "moving half as much; above -1). keep \"shown\" (the default): each stays where it shows in the export at "
             "`at` (its x, y and scale change to match, every key included); a pinned layer has no parallax, so only "
             "its depth changes. keep \"values\": only the depth changes. An animated depth gets a key at `at`.",
             target=F.PLACED, label="Set depth", importance="secondary", valid_when=TOP,
             params=[Param.number("depth", label="Depth", min=-0.99, max=1000, required=True), KEEP, AT])
def layer_set_depth(ctx, targets, args):
    new = float(args["depth"])
    for lid in targets:
        layer = ctx.item(lid)
        timed, cam, old, t = _now(ctx, lid, args.get("at", 0.0))
        if abs(new - old) < 1e-12:
            continue
        if args.get("keep", "shown") == "shown" and not layer.get("screenLock"):
            m = place.then(view.layer_matrix(timed, cam, {"depth": old}),
                           place.inverse(view.layer_matrix(timed, cam, {"depth": new})))
            place.carry(ctx, lid, m)
        if layer.get("screenLock"):                 # no parallax while pinned (its Depth isn't shown): the number only
            ctx.set(lid, "depth", new)
            continue
        own = t - retime.offset_of(ctx.doc, lid, _times(ctx))       # a keyed depth: its key at `at`, own seconds
        R.get("value.set").fn(ctx, [lid], {"prop": "depth", "v": new, "at": own})
