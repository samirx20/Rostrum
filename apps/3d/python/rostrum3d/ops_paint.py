"""Project a picture (brief 21): `paint.project` puts a picture on meshes and clays from a camera, as a paint layer on
each (paint_fields.LAYER `projectSource` and its camera, `project…`). The camera is a shot's at a frame, or a free
one (eye, target, fov, picture size). The picture is laid on the texels that camera sees when the paint is made
(paint_view.splat), so it lives on the surfaces: seen from another camera it shows their depth. "2d:<id>" is that 2D
item's newest pictures render, so repainting and rendering it again in Rostrum2D updates the projection.
"""
from __future__ import annotations

import math
from pathlib import Path

import rostrum_paint.ops as kit_ops
from rostrum_core import Param, project
from rostrum_core.errors import codes

from . import aim
from .kind import REGISTRY as R
from .paint_fields import CHANNELS, LAYER
from .paint_view import camera_fields
from .resolve import Frames

XYZ = dict(min_items=3, max_items=3, unit="m")


def shot_pose(data: dict, shot: dict, frame=None, width=None, height=None) -> dict:
    """{eye, target, fov, width, height, frame} of `shot`'s camera at `frame` (the shot's frames; default its start) as
    a free camera, for a `width` × `height` picture (default the shot's size): what a view stroke or a projection keeps.
    The one way a shot camera becomes a view (paint.project here, look_at's `view` for agents). ValueError: no camera."""
    cam = shot.get("camera")
    if not cam:
        raise ValueError(f'shot "{shot["id"]}" has no camera')
    fps = float(shot.get("fps", 24))
    f = round(shot.get("start", 0.0) * fps) if frame is None else int(frame)
    at = round(f / fps * 1000)
    fr = Frames(data, range(at, at + 1), 1000.0)
    world, v = fr.world(cam, at), fr.values(cam, at)
    w, h = int(width or shot.get("width", 1920)), int(height or shot.get("height", 1080))
    eye = aim.point(world, [0.0, 0.0, 0.0])
    fov = math.degrees(2 * math.atan(v["sensorWidth"] * h / w / 2 / v["focalLength"]))
    return {"eye": [round(x, 6) for x in eye], "target": [round(x, 6) for x in aim.point(world, [0.0, 0.0, -1.0])],
            "fov": round(fov, 4), "width": w, "height": h, "frame": f}


def _shot_view(ctx, shot_id: str, frame) -> dict:
    shot = ctx.item(shot_id)
    if shot.get("type") != "shot":
        ctx.fail(codes.BAD_ARGUMENT, '"shot"', f'"{shot_id}" is a {shot.get("type")}, not a shot')
    if not shot.get("camera"):
        ctx.fail(codes.BAD_ARGUMENT, f'shot "{shot_id}"', "has no camera", hint="Give it one with shot.set camera.")
    return shot_pose(ctx.doc, shot, frame)


def _check_picture(ctx, picture: str) -> None:
    folder = getattr(ctx.doc, "folder", None)
    if picture.startswith("2d:"):
        if folder:
            it = project.item(folder, picture[3:])          # loud, listing the project's items, when there is none
            if it["kind"] != "2d":
                ctx.fail(codes.BAD_ARGUMENT, '"picture"', f'"{picture[3:]}" is a {it["kind"]} item, not a 2D one')
        return
    f = Path(picture)
    f = f if f.is_absolute() or not folder else Path(folder) / f
    if not f.is_file():
        ctx.fail(codes.NOT_FOUND, '"picture"', f"{picture} is not there ({f})",
                 hint='Give a picture file (PNG, JPEG …) or "2d:<2D item id>".')


@R.operation("paint.project", "Project a picture onto meshes and clays from a camera (\"Project a picture from <shot>\"): "
             "a paint layer on each, on top, holding the picture where that camera sees the item (what is hidden "
             "behind something or faces away stays unpainted); the layer's own strokes paint over it. The camera: "
             "`shot` (its camera at `frame`, default the shot's start) or `eye` + `target` + `fov` + `width` + `height`. "
             "`picture`: a file, or \"2d:<2D item id>\" for that item's newest pictures render (render it again in "
             "Rostrum2D and the projection follows). One change for every target.",
             target=("mesh", "clay"), label="Project a picture", importance="secondary",
             params=[Param.text("picture", label="Picture", required=True,
                                help='A picture file, or "2d:<2D item id>" (its newest pictures render, first frame)'),
                     Param.id("shot", kind="shot", label="From shot", help="Project from this shot's camera"),
                     Param.number("frame", label="Frame", min=0, max=10_000_000, integer=True,
                                  help="The shot's frame its camera is taken at (default: the shot's start)"),
                     Param.list("eye", "number", label="Camera at", **XYZ, help="A free camera instead of a shot: where it stands"),
                     Param.list("target", "number", label="Looking at", **XYZ, help="… the point in the middle of the picture"),
                     Param.number("fov", label="Field of view", min=0.1, max=179, unit="°", help="… its vertical angle"),
                     Param.number("width", label="Width", min=1, max=16384, integer=True, unit="px", help="… picture width"),
                     Param.number("height", label="Height", min=1, max=16384, integer=True, unit="px", help="… picture height"),
                     Param.text("name", label="Name", help='The new layers\' name (default "Projected <picture>")'),
                     Param.choice("channel", list(CHANNELS), label="Paints", labels={k: v[0] for k, v in CHANNELS.items()},
                                  help="The surface channel the picture paints (default Colour)")])
def paint_project(ctx, targets, args):
    free = [k for k in ("eye", "target", "fov", "width", "height") if k in args]
    if bool(args.get("shot")) == bool(free):
        ctx.fail(codes.BAD_ARGUMENT, "shot / eye", "needs a shot or a free camera (eye, target, fov, width, height)",
                 hint="Give `shot`, or all of eye, target, fov, width, height.")
    if free and len(free) < 5:
        ctx.fail(codes.BAD_ARGUMENT, "eye", f'a free camera needs eye, target, fov, width and height (got {", ".join(free)})')
    view = _shot_view(ctx, args["shot"], args.get("frame")) if args.get("shot") else \
        {**{k: args[k] for k in free}, "frame": int(args.get("frame", 0))}
    _check_picture(ctx, args["picture"])
    name = args.get("name") or f'Projected {Path(args["picture"].removeprefix("2d:")).stem}'
    values = {"name": name, "channel": args.get("channel", "colour"), "projectSource": args["picture"],
              **camera_fields(view, "project")}
    made = []
    for t in targets:
        layer = kit_ops.build("paint", ctx.new_id("paint"), values, ctx.where, LAYER)
        ctx.insert(t, "paints", layer)
        made.append(layer["id"])
    return {"layers": made, "camera": view}
