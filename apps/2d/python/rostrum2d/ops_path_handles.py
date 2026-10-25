"""The path a moving layer or the frame travels between its position keys: `key.path_handles` bends it with spatial
Bézier handles, written on the x and y keys at one time as their `out` (leaving) and `in` (arriving) offsets
(rostrum_core.keys.spatial). One operation, one undo step.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.edits import MISSING
from rostrum_core.errors import codes
from rostrum_core.keys import keys_of
from rostrum_core.keys.marked import same_time

from . import fields as F
from .kind import REGISTRY as R

_HANDLE = dict(item="number", min_items=2, max_items=2, importance="primary")


def _key_at(owner: dict, prop: str, t: float) -> dict | None:
    return next((k for k in keys_of(owner, prop) if same_time(k["t"], t)), None)


@R.operation("key.path_handles", "Bend the path a layer or the frame travels at its position key at time t: `out` "
             "is the handle leaving the key and `in` the one arriving at it, each [dx, dy] in px from the key's "
             "place (null removes it: a third of the way to the neighbouring key, so a straight line when both "
             "ends have none). The x key gets dx and the y key dy. Give x and y keys the same ease for a true curve; "
             "speed along the curve follows the ease, not the distance. look_motion (what: path) shows the path.",
             target=F.LAYERS, label="Path handles", importance="secondary",
             params=[Param.number("t", label="Time", required=True, unit="s", min=-36000, max=36000,
                                  help="The time of the x and y keys (the layer's own seconds)"),
                     Param.list("out", label="Handle out", nullable=True, help="[dx, dy] px, or null to remove", **_HANDLE),
                     Param.list("in", label="Handle in", nullable=True, help="[dx, dy] px, or null to remove", **_HANDLE)])
def key_path_handles(ctx, targets, args):
    if "out" not in args and "in" not in args:
        ctx.fail(codes.BAD_ARGUMENT, '"out" / "in"', "neither is given: nothing to change",
                 hint="Give out, in or both: [dx, dy] in px, or null to remove.")
    for target in targets:
        owner = ctx.item(target)
        keys = {prop: _key_at(owner, prop, args["t"]) for prop in ("x", "y")}
        if not all(keys.values()):
            missing = " and ".join(p for p, k in keys.items() if k is None)
            ctx.fail(codes.BAD_ARGUMENT, f"{target} at {args['t']:g} s", f"has no {missing} key there",
                     hint="Key its position (x and y) at that time first, e.g. key.add fields: \"pose\".",
                     plain=f"{target} has no position key at {args['t']:g} s to bend the path at.")
        for side in ("out", "in"):
            if side not in args:
                continue
            for axis, (prop, key) in enumerate(keys.items()):
                if args[side] is None:
                    if side in key:
                        ctx.set(key["id"], side, MISSING)
                else:
                    ctx.set(key["id"], side, float(args[side][axis]))
