"""Clay operations (CL1): make a clay, join or carve pieces, record a brush stroke, remove a step. Each is one
operation, so one undo step in the one history; a step's settings are `claystep.set` and the clay's own (brush,
detail, material) are `clay.set`, both from the fields table (kind.py). The core builds the shape from the steps.

Drawing and spinning (clay.draw, clay.spin, clay.add's draw= / spin=) and Turn into clay are ops_clay_make.py; what a
new step holds is clay_steps.py, the one rule for operations and scripts.

Step ids: an operation counts `<clay>.step_N`; a script counts `<clay>.sN` (script.py), so a person's steps and a
script's never take each other's ids, and a script re-run keeps the person's steps (rostrum_core.merge).
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param, ids
from rostrum_core.errors import codes

from . import build, clay_detail, clay_steps as CS
from .clay_fields import BRUSHES, SYMMETRY
from .kind import REGISTRY as R
from .material_starts import STARTS, start_values
from .ops_items import PLACE, _holder, new_item

V3 = lambda name, label, required=False, help="": Param.list(name, "number", label=label, min=-1e5, max=1e5,  # noqa: E731
                                                            min_items=3, max_items=3, required=required, help=help)
AT = V3("at", "At", True, "The centre, in the clay's own space (clay.add: in the scene, or inside `into`)")
TO = V3("to", "To", help="Give it to make a capsule from `at` to here")
RADIUS = Param.number("radius", label="Radius", min=0.0001, max=100, unit="m", default=CS.RADIUS)
MODE = Param.choice("mode", ["add", "carve"], label="Mode", default="add", help="Add joins it on; Carve cuts it out")
BLEND = Param.number("blend", label="Blend", min=0, max=100, unit="m",
                     help="How softly it joins (metres); half the radius when left out")
SYM = Param.choice("symmetry", SYMMETRY, label="Mirror", help="x = mirrored across the clay's X = 0; the clay's own "
                   "setting when left out")
NAME = Param.text("name", label="Name", help='A word for the step ("body", "nose")')
LAYER = Param.text("layer", label="Layer", help='The sculpt layer it goes on ("" = the Base); the clay sculptLayer '
                   "when left out (claylayer.add)")


def add_step(ctx, clay: str, values: dict) -> dict:
    """Append one step to a clay; its id counted per clay (`<clay>.step_N`)."""
    item = ctx.item(clay)
    if item["type"] != "clay":
        ctx.fail(codes.BAD_ARGUMENT, f'target "{clay}"', f"is a {item['type']}, not a clay")
    step = build.make("claystep", ids.counted(ctx.idx, f"{clay}.step"), {"name": "", **values}, ctx.where)
    ctx.insert(clay, "steps", step)
    return step


piece_values, stroke_values, PATHS = CS.piece_values, CS.stroke_values, CS.PATHS    # script.py's too


def grain(ctx, clay: dict) -> float:
    """The clay's detail now (its smallest grain): what makes a drawing tiny."""
    return clay_detail.detail(ctx.doc, clay)


def clay_material(ctx) -> str:
    """The project's material named "Clay", made from the Clay start the first time (SPEC §5: a new clay starts as
    Clay, grey): every clay made without a material shares it, so one change recolours them all until one is given
    its own (material.split). Renamed, it is the person's own material and the next clay makes a new "Clay"."""
    label = STARTS["clay"]["label"]
    for m in ctx.doc.get("materials", []):
        if m.get("name") == label:
            return m["id"]
    item = new_item(ctx, "material", {"name": label}, start_values("clay", {}))
    ctx.insert("root", "materials", item)
    return item["id"]


def _piece(ctx, clay: str, args: dict, shape: str):
    return add_step(ctx, clay, piece_values(ctx.item(clay), args, shape))


PTS = lambda name, label, help: Param.points(name, label=label, min=3, max=3, help=help)  # noqa: E731
DRAW = PTS("draw", "Draw", "[[x, y, z], …] an outline (4 points or more; closed last → first) in the scene, or "
           "inside `into`: the clay starts as it, puffed up (instead of a ball at `at`)")
SPIN = PTS("spin", "Spin", "[[x, y, z], …] half a profile (2 points or more): the clay starts as it, spun round `axis`")
FACING = V3("facing", "Facing", help="A drawing's plane normal, pointing at the viewer: the side drawn on becomes the "
            "clay's front (its +Z). Left out: the outline's own plane")
AXIS = PTS("axis", "Axis", "[[x, y, z], [x, y, z]] two points on the spin axis; left out: straight up through the "
           "profile's first point")
PUFF = Param.number("puff", label="Puff", min=0.1, max=3, default=1.0,
                    help="How thick a drawn shape is: 1 = round (as thick in the middle as the outline is wide "
                         "there), less is flatter, more is fatter")


@R.operation("clay.add", "Add a clay: a lump to sculpt. It starts as one of: a sphere of `radius` at `at`; a drawn "
             "outline puffed up (`draw`: scene points, + `facing`, `puff`); or half a profile spun round an axis "
             "(`spin`, + `axis`). Drawn or spun, the clay stands at the drawing's middle (horizontally centred, at "
             "its lowest point), turned about Y so its X runs along the drawing: Mirror's X = 0 runs down its "
             "middle. A tiny drawing (under 4 points, or thinner than 1.5 grains) makes a lump of `radius` (else "
             "3 cm) instead. Its detail (the smallest grain) follows the shot cameras (clay.set detailMode=fixed "
             "detail=… fixes it); its brush is a quarter of its size. Then clay.draw / clay.spin / clay.lump join "
             "more, clay.stroke sculpts it. Without `material` it gets the project's \"Clay\" material (made from the "
             "Clay start the first time, shared by every clay made so).", label="Add clay",
             params=[*PLACE, dataclasses.replace(AT, required=False), RADIUS, DRAW, SPIN, FACING, AXIS, PUFF, SYM,
                     Param.text("material", label="Material", kind="material")])
def clay_add(ctx, targets, args):
    sym = args.get("symmetry") or "x"
    given = [k for k in ("at", "draw", "spin") if args.get(k)]
    if len(given) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "the clay", f"starts from exactly one of at, draw or spin; got "
                 f"{', '.join(given) or 'none'}", hint="at=[x, y, z] for a ball, draw=[[x, y, z], …] for a drawn shape.")
    if args.get("at"):
        r = args.get("radius") or CS.RADIUS
        x, y, z = (float(v) for v in args["at"])
        placed, size = {"x": x, "y": y, "z": z}, r
        made = piece_values({"symmetry": sym}, {"at": [0.0, 0.0, 0.0], "radius": r}, "sphere")
    else:
        placed, local = CS.standing(args)
        start = {"symmetry": sym, "brushSize": args.get("radius") or CS.DEFAULT["brushSize"]}
        made = (CS.draw_values if args.get("draw") else CS.spin_values)(start, local, local["points"],
                                                                         CS.DEFAULT["detail"])
        size = CS.size_of(made)
    fields = {**placed, "symmetry": sym,
              "brushSize": round(max(size / 4, 0.0005), 4),     # a quarter of the clay: big enough to shape it,
                                                                 # small enough to stay within a frame (proof: medium dab)
              "material": args.get("material") or clay_material(ctx)}
    item = new_item(ctx, "clay", args, fields)
    parent, key = _holder(ctx, args.get("into"))
    ctx.insert(parent, key, item, args.get("index"))
    add_step(ctx, item["id"], made)
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
             "where a ray along dir meets the clay (in its own space). Settings left out are the clay's brush settings. "
             "brush=mask paints a mask that protects the clay from every other brush; invert=true is Ctrl's opposite "
             "(flatten puffs out, crease pinches to a ridge, mask takes the mask away).",
             target="clay", label="Sculpt",
             params=[Param.choice("brush", BRUSHES, label="Brush"),
                     Param.number("size", label="Size", min=0.0005, max=10, unit="m", help="The brush's radius"),
                     Param.number("strength", label="Strength", min=0, max=1), SYM,
                     Param.toggle("accumulate", label="Build up"),
                     Param.number("falloff", label="Falloff", min=0, max=1, help="0 = soft edge, 1 = hard edge"),
                     Param.number("spacing", label="Spacing", min=0.05, max=1,
                                  help="Dab spacing, as a share of the radius"),
                     Param.toggle("frontOnly", label="Front faces only",
                                  help="Skip a dab that would land on a surface facing away from the view"),
                     Param.toggle("invert", label="Opposite", help="Ctrl's opposite: flatten puffs, crease pinches, "
                                  "mask unmasks"),
                     Param.text("dabs", label="Dabs", help='"clay/<hash>.dabs" (a file in the project)'),
                     Param.points("dabList", label="Dabs (inline)", min=9, max=11,
                                  help="[ax, ay, az, nx, ny, nz, bx, by, bz] each, + [radiusScale, strengthScale] "
                                       "with a pen"),
                     Param.points("path", label="Path", min=3, max=3, help="[x, y, z] points"),
                     V3("dir", "Direction", help="The way the rays point, e.g. [0, 0, -1]"), NAME, LAYER])
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
