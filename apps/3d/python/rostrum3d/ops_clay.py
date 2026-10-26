"""Clay operations (CL1): make a clay, join or carve pieces, record a brush stroke, remove a step. Each is one
operation, so one undo step in the one history; a step's settings are `claystep.set` and the clay's own (brush,
detail, material) are `clay.set`, both from the fields table (kind.py). The core builds the shape from the steps.

Step ids: an operation counts `<clay>.step_N`; a script counts `<clay>.sN` (script.py), so a person's steps and a
script's never take each other's ids, and a script re-run keeps the person's steps (rostrum_core.merge).
"""
from __future__ import annotations

from rostrum_core import Param, ids
from rostrum_core.errors import codes

from . import build, fields as F
from .clay_fields import BRUSHES, SYMMETRY
from .kind import REGISTRY as R
from .ops_items import PLACE, _holder, new_item

V3 = lambda name, label, required=False, help="": Param.list(name, "number", label=label, min=-1e5, max=1e5,  # noqa: E731
                                                            min_items=3, max_items=3, required=required, help=help)
AT = V3("at", "At", True, "The centre, in the clay's own space (clay.add: in the scene, or inside `into`)")
TO = V3("to", "To", help="Give it to make a capsule from `at` to here")
RADIUS = Param.number("radius", label="Radius", min=0.0001, max=100, unit="m", default=0.15)
MODE = Param.choice("mode", ["add", "carve"], label="Mode", default="add", help="Add joins it on; Carve cuts it out")
BLEND = Param.number("blend", label="Blend", min=0, max=100, unit="m",
                     help="How softly it joins (metres); half the radius when left out")
SYM = Param.choice("symmetry", SYMMETRY, label="Mirror", help="x = mirrored across the clay's X = 0; the clay's own "
                   "setting when left out")
NAME = Param.text("name", label="Name", help='A word for the step ("body", "nose")')


def add_step(ctx, clay: str, values: dict) -> dict:
    """Append one step to a clay; its id counted per clay (`<clay>.step_N`)."""
    item = ctx.item(clay)
    if item["type"] != "clay":
        ctx.fail(codes.BAD_ARGUMENT, f'target "{clay}"', f"is a {item['type']}, not a clay")
    step = build.make("claystep", ids.counted(ctx.idx, f"{clay}.step"), {"name": "", **values}, ctx.where)
    ctx.insert(clay, "steps", step)
    return step


def piece_values(clay: dict, args: dict, shape: str) -> dict:
    """A piece step's values: what was given, else the blend at half the radius and the clay's own mirror (the one
    rule for operations and scripts)."""
    r = args.get("radius", RADIUS.default)
    values = {"step": "piece", "shape": shape, "at": args["at"], "radius": r, "mode": args.get("mode") or "add",
              "blend": args["blend"] if args.get("blend") is not None else round(r * 0.5, 6),
              "symmetry": args.get("symmetry") or clay["symmetry"], "name": args.get("name") or ""}
    if shape == "capsule":
        values["to"] = args["to"]
    return values


STROKE_FROM_CLAY = {"brush": "brush", "size": "brushSize", "strength": "brushStrength", "symmetry": "symmetry",
                    "accumulate": "accumulate"}
PATHS = ("dabs", "dabList", "path")


def stroke_values(clay: dict, args: dict) -> dict:
    """A stroke step's values: the settings given, else the clay's brush settings; its one path (dabs or path + dir)."""
    values = {k: args[k] if args.get(k) is not None else clay[own] for k, own in STROKE_FROM_CLAY.items()}
    values.update({k: args[k] for k in (*PATHS, "dir") if args.get(k)})
    return {"step": "stroke", "name": args.get("name") or "", **values}


def _piece(ctx, clay: str, args: dict, shape: str):
    return add_step(ctx, clay, piece_values(ctx.item(clay), args, shape))


@R.operation("clay.add", "Add a clay: a lump to sculpt, starting as one sphere of `radius` at `at`. Its detail (the "
             "smallest grain) is radius / 100, its brush a quarter of the radius. Then clay.lump joins more, clay.stroke sculpts it.", label="Add clay",
             params=[*PLACE, AT, RADIUS, SYM, Param.text("material", label="Material", kind="material")])
def clay_add(ctx, targets, args):
    r = args.get("radius", RADIUS.default)
    detail = min(0.05, max(0.0002, round(r / 100, 4)))
    x, y, z = (float(v) for v in args["at"])
    fields = {"x": x, "y": y, "z": z, "detail": detail, "symmetry": args.get("symmetry") or "x",
              "brushSize": round(max(r / 4, 0.0005), 4),          # a quarter of the clay: big enough to shape it,
                                                                   # small enough to stay within a frame (proof: medium dab)
              "material": args.get("material") or ""}
    item = new_item(ctx, "clay", args, fields)
    parent, key = _holder(ctx, args.get("into"))
    ctx.insert(parent, key, item, args.get("index"))
    _piece(ctx, item["id"], {"at": [0.0, 0.0, 0.0], "radius": r, "symmetry": fields["symmetry"]}, "sphere")
    return item


@R.operation("clay.lump", "Join a lump onto a clay (or carve one out, mode=carve): a sphere at `at`, or a capsule "
             "from `at` to `to`; positions in the clay's own space.", target="clay", label="Add lump",
             params=[AT, TO, RADIUS, MODE, BLEND, SYM, NAME])
def clay_lump(ctx, targets, args):
    for t in targets:
        _piece(ctx, t, args, "capsule" if args.get("to") else "sphere")


@R.operation("clay.shape", "Add an exact piece to a clay: a sphere or capsule, joined or carved, with its blend and "
             "mirror; positions in the clay's own space.", target="clay", label="Add piece",
             params=[Param.choice("shape", ["sphere", "capsule"], label="Shape", required=True), AT, TO, RADIUS, MODE,
                     BLEND, SYM, NAME])
def clay_shape(ctx, targets, args):
    if args["shape"] == "capsule" and not args.get("to"):
        ctx.fail(codes.BAD_ARGUMENT, '"to"', "is required for a capsule", hint="Give its other end, [x, y, z].")
    for t in targets:
        _piece(ctx, t, args, args["shape"])


@R.operation("clay.stroke", "Sculpt a clay with one brush stroke. Give the dabs as applied (`dabs`, a file reference "
             "a live stroke made, or `dabList` inline), or a world stroke: `path` points and `dir`, each dab landing "
             "where a ray along dir meets the clay (in its own space). Settings left out are the clay's brush settings.",
             target="clay", label="Sculpt",
             params=[Param.choice("brush", BRUSHES, label="Brush"),
                     Param.number("size", label="Size", min=0.0005, max=10, unit="m", help="The brush's radius"),
                     Param.number("strength", label="Strength", min=0, max=1), SYM,
                     Param.toggle("accumulate", label="Build up"),
                     Param.text("dabs", label="Dabs", help='"clay/<hash>.dabs" (a file in the project)'),
                     Param.points("dabList", label="Dabs (inline)", min=9, max=9,
                                  help="[ax, ay, az, nx, ny, nz, bx, by, bz] each"),
                     Param.points("path", label="Path", min=3, max=3, help="[x, y, z] points"),
                     V3("dir", "Direction", help="The way the rays point, e.g. [0, 0, -1]"), NAME])
def clay_stroke(ctx, targets, args):
    path = [k for k in PATHS if args.get(k)]
    if len(path) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "the stroke", f"needs exactly one of dabs, dabList or path; got {', '.join(path) or 'none'}",
                 hint="A live stroke gives dabs; an agent gives path + dir.")
    if path == ["path"] and not args.get("dir"):
        ctx.fail(codes.BAD_ARGUMENT, '"dir"', "is required with a path", hint="The way the rays point, e.g. [0, 0, -1].")
    for t in targets:
        add_step(ctx, t, stroke_values(ctx.item(t), args))


@R.operation("claystep.remove", "Remove steps from a clay (a piece or a stroke); the clay is rebuilt without them.",
             target="claystep", label="Remove step")
def claystep_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)
