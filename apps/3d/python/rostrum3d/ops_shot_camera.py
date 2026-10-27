"""Moving a shot's own camera in one step (SPEC 3d-simplicity §5 "The camera that frames itself"):

- `shot.take_view`: the camera stands at a view's place, looks at its middle, with its lens ("Make this the shot").
- `shot.frame`: the camera keeps its direction and lens and moves so the items sit in the middle of the frame and
  fill it with a margin ("Frame the selection"); aimed at an item, it only slides along its view line.

Both write the camera in its parent's space at the time asked (inside a group or on a rig it stays there), so the
picture is the one asked for. An aimed camera keeps aiming: take_view aims it at the view's middle (an aim at an item
becomes an aim at that point: the view asked for wins; one undo brings the item back). A field that has keys gets a
key at that time instead of a new still value (a still value under keys would change nothing).
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes

from . import aim, item_bounds
from .kind import REGISTRY as R
from .ops_keys import put_key
from .resolve import Frames

FILL = 0.8          # the items take 80 % of the frame on their tighter side: a 10 % margin all round
POINT = lambda name, label, help: Param.list(name, "number", label=label, min_items=3, max_items=3, unit="m",  # noqa: E731
                                             required=True, help=help)
AT = Param.number("at", label="At", min=0, max=36000, unit="s",
                  help="The time (seconds) to set it at; it matters only for a camera that moves. Default: the shot's start")


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def _unit(v) -> list[float]:
    n = math.hypot(*v) or 1.0
    return [x / n for x in v]


def _shot_camera(ctx, targets) -> tuple[dict, str]:
    if len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "target", f"needs one shot (got {len(targets)})")
    shot = ctx.item(targets[0])
    if not shot.get("camera"):
        ctx.fail(codes.BAD_ARGUMENT, f'shot "{shot["id"]}"', "has no camera to move", hint="Give it one with shot.set camera.")
    return shot, shot["camera"]


def _put(ctx, cam: str, values: dict, at: float):
    """Each field: a key at `at` when it has keys, else its still value."""
    keyed = {k["prop"] for k in ctx.item(cam).get("keys", [])}
    for prop, v in values.items():
        if prop in keyed:
            put_key(ctx, cam, prop, at, {"v": v})
        else:
            ctx.set(cam, prop, v)


def _place(fr: Frames, cam: str, f: int, eye) -> tuple[tuple, dict]:
    """(the parent's world transform, the camera's x y z there) for a world point."""
    parent = fr.parent[cam]
    pw = fr.world(parent, f) if parent else aim.IDENTITY
    local = aim.point(aim.invert(pw), list(eye))
    return pw, {k: round(v, 6) for k, v in zip("xyz", local)}


def _frames(ctx, shot: dict, args: dict) -> tuple[float, int, Frames]:
    at = float(args.get("at", shot.get("start", 0.0)))
    f = round(at * 1000)
    return at, f, Frames(ctx.doc, range(f, f + 1), 1000.0)


@R.operation("shot.take_view", "Move a shot's own camera to a view in one step (\"Make this the shot\"): it stands at "
             "`position`, looks at `lookAt` (both world, metres) with `focalLength`. Inside a group or on a rig it "
             "stays there; an aimed camera aims at `lookAt`; a field with keys gets a key at `at`. One undo takes it back. "
             "To frame items instead, use shot.frame; for a new camera and shot, shot.from_view.",
             target="shot", label="Make this the shot",
             params=[POINT("position", "Position", "Where the camera stands (x y z, world)"),
                     POINT("lookAt", "Look at", "The point in the middle of the picture (x y z, world)"),
                     Param.number("focalLength", label="Focal length", min=1, max=2000, unit="mm", required=True), AT])
def shot_take_view(ctx, targets, args):
    shot, cam = _shot_camera(ctx, targets)
    at, f, fr = _frames(ctx, shot, args)
    eye, look = [float(x) for x in args["position"]], [float(x) for x in args["lookAt"]]
    if math.dist(eye, look) < 1e-6:
        ctx.fail(codes.BAD_ARGUMENT, '"lookAt"', "is where the camera stands; give a point in front of it")
    pw, values = _place(fr, cam, f, eye)
    item = ctx.item(cam)
    if item.get("aim", "none") == "none":
        turn = aim.aim_rotation(pw, [values[k] for k in "xyz"], look)
        values.update({k: round(v, 4) for k, v in zip(("rx", "ry", "rz"), turn)})
    else:
        if item["aim"] == "item":
            ctx.set(cam, "aim", "point")
        values.update({"aimX": look[0], "aimY": look[1], "aimZ": look[2], "roll": 0.0})
    values["focalLength"] = round(float(args["focalLength"]), 2)
    _put(ctx, cam, values, at)


def slide(base, axes, corners, tan_w: float, tan_h: float, near: float) -> float:
    """How far forward from `base` along the view line (axes: right, up, forward, unit) a camera stands so every corner
    sits inside the frame shrunk to FILL, the tightest one on its edge; negative = back."""
    right, up, fwd = axes
    out = math.inf
    for p in corners:
        d = [a - b for a, b in zip(p, base)]
        need = max(abs(_dot(d, right)) / (tan_w * FILL), abs(_dot(d, up)) / (tan_h * FILL), near)
        out = min(out, _dot(d, fwd) - need)
    return out


@R.operation("shot.frame", "Frame items with a shot's own camera in one step (\"Frame the selection\"): the camera keeps "
             "the way it looks and its lens and moves so the items sit in the middle of the picture and fill it with a "
             "10 % margin (a camera aimed at a point: the point moves with it; aimed at an item: it moves only along its "
             "view line, nearer or farther, so it keeps looking at that item). Inside a group or on a rig it stays "
             "there; a field with keys gets a key at `at`; with depth of field (no Focus on item) the items' middle "
             "is made sharp. One undo takes it back. To turn the camera too, use shot.take_view.",
             target="shot", label="Frame the selection",
             params=[Param.list("items", "text", label="Items", min_items=1, required=True,
                                help="The ids of the items to frame (shapes, clay, groups, copies, lights …)"), AT])
def shot_frame(ctx, targets, args):
    shot, cam = _shot_camera(ctx, targets)
    at, f, fr = _frames(ctx, shot, args)
    for i in args["items"]:
        ctx.item(i)
    try:
        lo, hi = item_bounds.world_box(ctx.doc, list(args["items"]), at)
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, '"items"', str(e))
    world, v = fr.world(cam, f), fr.values(cam, f)
    eye = aim.point(world, [0.0, 0.0, 0.0])
    axes = [_unit([a - b for a, b in zip(aim.point(world, d), eye)]) for d in ([1, 0, 0], [0, 1, 0], [0, 0, -1])]
    tan_w = v["sensorWidth"] / (2 * v["focalLength"])
    tan_h = tan_w * shot.get("height", 1080) / shot.get("width", 1920)
    corners = [[(lo, hi)[i >> k & 1][k] for k in range(3)] for i in range(8)]
    mid = [(a + b) / 2 for a, b in zip(lo, hi)]
    base = eye if v["aim"] == "item" else mid          # an item's aim rules the direction: only along the line
    t = slide(base, axes, corners, tan_w, tan_h, 2 * v["near"])
    new_eye = [b + t * a for b, a in zip(base, axes[2])]
    values = _place(fr, cam, f, new_eye)[1]
    if v["aim"] == "point":
        values.update({f"aim{k}": round(v[f"aim{k}"] + n - e, 6) for k, n, e in zip("XYZ", new_eye, eye)})
    elif v["aim"] == "item" and _dot([a - b for a, b in zip(aim.point(fr.world(v["aimItem"], f), [0.0, 0.0, 0.0]),
                                                              new_eye)], axes[2]) <= 1e-3:
        ctx.fail(codes.BAD_ARGUMENT, f'camera "{cam}"', f'would pass "{v["aimItem"]}", which it aims at, and turn round',
                 hint="Stop aiming (item.aim off) or aim at a point, and frame again.")
    if v.get("dof") and not v.get("focusItem"):
        values["focusDistance"] = round(max(0.001, _dot([a - b for a, b in zip(mid, new_eye)], axes[2])), 4)
    _put(ctx, cam, values, at)
