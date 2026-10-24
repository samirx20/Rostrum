"""Putting a camera on a rig in one step (SPEC §8 Rigs): `rig.wrap` makes a rig where the camera is, moves the camera
onto its head and sets the rig's numbers so the camera starts exactly where it was; `rig.turn_once` keys an orbit's
angle once round over a shot (a turntable). The rig itself is rigs.py / rig_fields.py.

Where the camera starts, in its parent's space (all at time 0, aims resolved):
  orbit  the rig's base is the centre (`around`: an item's origin or a point); radius, height and angle put the head
         on the camera; the head faces the centre;
  crane  the arm (2 m, level) reaches forward to the camera; the base turns the way the camera looks; tilt = its pitch;
  dolly  the track starts at the camera and runs the way it looks; tilt = its pitch.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import aim, build, fields as F
from .compile import world_at_start
from .kind import REGISTRY as R
from .ops_items import refuse_used_id
from .ops_keys import put_key
from .rig_fields import RIG_KINDS

TRANSFORM_KEYS = ("x", "y", "z", "rx", "ry", "rz")
ARM = 2.0                                           # a new crane's arm (metres)


def _parent_world(ctx, id_: str):
    parent = index(ctx.doc, ctx.kind.lists)[id_].parent
    return parent, (aim.IDENTITY if parent == "root" else world_at_start(ctx.doc, parent))


def _to_parent(pw, world_point):
    inv = aim._inverse(pw[0])
    return aim._apply(inv, [a - b for a, b in zip(world_point, pw[1])])


def _around(ctx, cam_id: str, args: dict, cam_world) -> list[float]:
    """The world point an orbit circles: `around` (an item's origin) or `point`, else what the camera aims at, else the
    point at its focus distance straight ahead."""
    if args.get("around"):
        ctx.item(args["around"])
        return aim.point(world_at_start(ctx.doc, args["around"]), [0.0, 0.0, 0.0])
    if args.get("point"):
        return list(args["point"])
    cam = ctx.item(cam_id)
    if cam.get("aim") == "item" and cam.get("aimItem"):
        return aim.point(world_at_start(ctx.doc, cam["aimItem"]), [0.0, 0.0, 0.0])
    if cam.get("aim") == "point":
        return [cam.get(f"aim{a}", 0.0) for a in "XYZ"]
    return aim.point(cam_world, [0.0, 0.0, -float(cam.get("focusDistance", 5.0))])


def placement(kind: str, cam: list[float], forward: list[float], centre: list[float] | None) -> dict:
    """The rig's fields (parent space) that put its head at `cam` looking along `forward` (or at `centre`, an orbit)."""
    if kind == "orbit":
        d = [c - o for c, o in zip(cam, centre)]
        return {"x": centre[0], "y": centre[1], "z": centre[2], "radius": math.hypot(d[0], d[2]), "height": d[1],
                "angle": math.degrees(math.atan2(d[0], d[2]))}
    fx, fy, fz = forward
    yaw, pitch = math.degrees(math.atan2(-fx, -fz)), math.degrees(math.atan2(fy, math.hypot(fx, fz)))
    out = {"ry": yaw, "tilt": max(-90.0, min(90.0, pitch))}
    if kind == "crane":                             # the head is ARM ahead of the base: the base sits behind the camera
        s, c = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
        return {**out, "x": cam[0] + ARM * s, "y": cam[1], "z": cam[2] + ARM * c, "armLength": ARM}
    return {**out, "x": cam[0], "y": cam[1], "z": cam[2]}


@R.operation("rig.wrap", "Put a camera on a new rig in one step: the rig is made where the camera is and the camera "
             "rides its head, starting exactly where it was (its own position keys are cleared). orbit circles "
             "`around` (an item) or `point` (else what the camera aims at); crane and dolly run the way the camera looks. "
             "handheld adds the gentle drift; turn=<shot id> keys one full orbit over that shot (a turntable).",
             target="camera", label="Put on a rig",
             params=[Param.choice("kind", RIG_KINDS, label="Rig", required=True),
                     Param.id("around", label="Around item"),
                     Param.list("point", "number", label="Around point", min_items=3, max_items=3, unit="m"),
                     Param.toggle("handheld", label="Handheld"),
                     Param.id("turn", label="Turn once over shot"),
                     Param.text("id", label="Rig id"), Param.text("name", label="Rig name")])
def rig_wrap(ctx, targets, args):
    if len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "target", f"needs one camera (got {len(targets)})")
    cam_id, kind = targets[0], args["kind"]
    parent, pw = _parent_world(ctx, cam_id)
    if parent != "root" and ctx.item(parent)["type"] == "rig":
        ctx.fail(codes.BAD_ARGUMENT, f'camera "{cam_id}"', f'already rides the rig "{parent}"',
                 hint="Change that rig's Rig setting, or move the camera out first (item.arrange).")
    if args.get("turn") and kind != "orbit":
        ctx.fail(codes.BAD_ARGUMENT, '"turn"', "only turns an orbit rig", hint='Give kind: "orbit".')
    cw = world_at_start(ctx.doc, cam_id)
    inv = aim._inverse(pw[0])
    cam = _to_parent(pw, aim.point(cw, [0.0, 0.0, 0.0]))
    forward = aim._apply(inv, aim._apply(cw[0], [0.0, 0.0, -1.0]))
    centre = _to_parent(pw, _around(ctx, cam_id, args, cw)) if kind == "orbit" else None
    rig_id = args.get("id") or ctx.new_id("rig")
    refuse_used_id(ctx, rig_id)
    name = args.get("name") or f"{kind.capitalize()} rig"
    rig = build.make("rig", rig_id, {"name": name, "rig": kind, "handheld": bool(args.get("handheld")),
                                     **placement(kind, cam, forward, centre)}, ctx.where)
    at = index(ctx.doc, ctx.kind.lists)[cam_id]
    ctx.insert(at.parent, at.key, rig, at.index)                  # where the camera was in its list
    for k in [k["id"] for k in ctx.item(cam_id).get("keys", []) if k["prop"] in TRANSFORM_KEYS]:
        ctx.remove(k)
    ctx.move(cam_id, rig_id, "children", None)
    for f in TRANSFORM_KEYS:
        ctx.set(cam_id, f, 0.0)
    if args.get("turn"):
        _turn(ctx, rig_id, args["turn"])


def _turn(ctx, rig_id: str, shot_id: str):
    shot = next((s for s in ctx.doc.get("shots", []) if s["id"] == shot_id), None)
    if shot is None:
        ctx.fail(codes.BAD_ARGUMENT, f'shot "{shot_id}"', "is not a shot in this document")
    rig = ctx.item(rig_id)
    if rig.get("rig") != "orbit":
        ctx.fail(codes.BAD_ARGUMENT, f'rig "{rig_id}"', f"is a {rig.get('rig')} rig; only an orbit turns once round")
    a0 = float(rig.get("angle", 0.0))
    put_key(ctx, rig_id, "angle", shot["start"], {"v": a0, "ease": "linear"})
    put_key(ctx, rig_id, "angle", shot["end"], {"v": a0 + 360.0, "ease": "linear"})


@R.operation("rig.turn_once", "Key an orbit rig's angle once round (360°, steady) from the start to the end of a shot: "
             "a turntable. The last frame stops just short of a full turn, so the shot loops.",
             target="rig", label="Turn once over the shot",
             params=[Param.id("shot", label="Shot", required=True)])
def rig_turn_once(ctx, targets, args):
    for t in targets:
        _turn(ctx, t, args["shot"])
