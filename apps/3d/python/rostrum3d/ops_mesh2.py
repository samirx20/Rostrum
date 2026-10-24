"""Editable mesh operations (SPEC §4.3, part 2): bevel and loop cut edges, the knife, a material per face, and sharp
edges for the smoothed surface. Each is one operation, so one undo step; what to change is named by a selector
(mesh_select.py). The geometry is poly_bevel.py and poly_cut.py; faceMaterials and creases follow every cut in one
place (mesh_book.py, through ops_mesh.store_change).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import mesh_book, poly, poly_bevel, poly_cut
from .kind import REGISTRY as R
from .ops_mesh import EDITABLE, FACES, pick, store_change

EDGES = Param.text("edges", label="Edges", required=True,
                   help='Which edges, by their two points: "edges 0-1 1-5" (the screen passes its selection)')


def _fail_geometry(ctx, what, e, hint):
    ctx.fail(codes.BAD_ARGUMENT, what, str(e), hint=hint)


@R.operation("edges.bevel", "Round the chosen edges with `segments` rows of faces (1: a flat chamfer), `width` "
             "metres in along each face. Where chosen edges meet at a corner the rounds meet in a clean mitre; a "
             "corner where three chosen edges meet gets one corner face. Answers with the new faces' selector.",
             target="mesh", label="Bevel", valid_when=EDITABLE,
             params=[EDGES, Param.number("width", label="Width", min=1e-6, max=1e3, step=0.0005, unit="m",
                                         default=0.001, help="How far in along each face the round starts"),
                     Param.number("segments", label="Segments", min=1, max=16, integer=True, default=1,
                                  help="Rows of faces across the round (1: a flat chamfer)")])
def edges_bevel(ctx, targets, args):
    item = ctx.item(targets[0])
    _, chosen = pick(ctx, item, args["edges"], "edges")
    try:
        change = poly_bevel.bevel(item["points"], poly.faces_of(item), chosen, args.get("width", 0.001),
                                  int(args.get("segments", 1)))
    except ValueError as e:
        _fail_geometry(ctx, '"width"', e, "Use the width it says fits, or less; or bevel fewer edges at once.")
    return {"faces": store_change(ctx, targets[0], change)}


@R.operation("edges.loopcut", "Cut the ring of four-sided faces across from one edge `count` times, evenly, all the "
             "way round (it stops at a face that isn't four-sided or at an open border). With one cut, `slide` (-1 to "
             "1) moves it towards one side. Answers with the cut faces' selector.",
             target="mesh", label="Loop cut", valid_when=EDITABLE,
             params=[Param.text("edges", label="Edge", required=True,
                                help='One edge the ring crosses: "edges 0-1"'),
                     Param.number("count", label="Cuts", min=1, max=64, integer=True, default=1),
                     Param.number("slide", label="Slide", min=-1, max=1, step=0.05, default=0.0,
                                  help="With one cut: -1 near one side, 0 the middle, 1 near the other")])
def edges_loopcut(ctx, targets, args):
    item = ctx.item(targets[0])
    _, chosen = pick(ctx, item, args["edges"], "edges")
    if len(chosen) != 1:
        ctx.fail(codes.BAD_ARGUMENT, f'"{args["edges"]}"', f"names {len(chosen)} edges; a loop cut starts from one",
                 hint='Name one edge the ring crosses, like "edges 0-1".')
    try:
        change = poly_cut.loopcut(item["points"], poly.faces_of(item), next(iter(chosen)), int(args.get("count", 1)),
                                  args.get("slide", 0.0))
    except ValueError as e:
        _fail_geometry(ctx, f'"{args["edges"]}"', e, "Pick an edge between four-sided faces.")
    return {"faces": store_change(ctx, targets[0], change)}


@R.operation("mesh.knife", "Cut faces along a stroke: `points` (at least 2, the item's own space, on or near the "
             "surface) seen along `view` (the looking direction). Each pair of points and the view make a cutting "
             "plane; every face facing the viewer that the stroke passes over is cut right across, with new points on "
             "the edges it crosses (shared, so the mesh stays joined). Fails if it cuts nothing. Answers with the cut "
             "faces' selector.", target="mesh", label="Knife", valid_when=EDITABLE,
             params=[Param.points("points", label="Stroke", min=3, max=3, required=True, help="[[x, y, z], …]"),
                     Param.list("view", "number", label="View", min=-1e5, max=1e5, min_items=3, max_items=3,
                                required=True, help="[x, y, z]: the direction you look along")])
def mesh_knife(ctx, targets, args):
    item, stroke = dict(ctx.item(targets[0])), args["points"]
    if len(stroke) < 2:
        ctx.fail(codes.BAD_ARGUMENT, '"points"', f"has {len(stroke)} point; a stroke needs 2 or more")
    cut = 0
    for p0, p1 in zip(stroke, stroke[1:]):
        try:
            change = poly_cut.knife(item["points"], poly.faces_of(item), p0, p1, args["view"])
            item.update(mesh_book.apply(item, change))
        except ValueError as e:
            _fail_geometry(ctx, '"points"', e, "Give points apart from each other across the view.")
        cut += len(change.kept)
    if not cut:
        ctx.fail(codes.BAD_ARGUMENT, '"points"', "cuts nothing: the stroke crosses no face facing the view",
                 hint="Put the points on the surface (look_at tells where), and view looking at those faces.")
    for k in ("points", "faceCounts", "faceIndices", "faceMaterials", "creases"):
        ctx.set(targets[0], k, item[k])
    return {"cuts": cut}


@R.operation("faces.material", "Give the chosen faces their own material (\"\" = back to the item's material).",
             target="mesh", label="Material", valid_when=EDITABLE,
             params=[FACES, Param.text("material", label="Material", required=True, help='A material id, or ""')])
def faces_material(ctx, targets, args):
    mat = args["material"]
    if mat and ctx.item(mat)["type"] != "material":
        ctx.fail(codes.BAD_ARGUMENT, f'material "{mat}"', f"is a {ctx.item(mat)['type']}, not a material")
    item = ctx.item(targets[0])
    _, chosen = pick(ctx, item, args["faces"], "faces")
    mats = list(item.get("faceMaterials") or [""] * len(item["faceCounts"]))
    for n in chosen:
        mats[n] = mat
    ctx.set(targets[0], "faceMaterials", mats if any(mats) else [])
    return {"faces": args["faces"]}


@R.operation("edges.sharp", "Keep the chosen edges sharp when the surface is smoothed (`sharp` false: let them "
             "round again).", target="mesh", label="Keep sharp", valid_when=EDITABLE,
             params=[EDGES, Param.toggle("sharp", label="Sharp", default=True)])
def edges_sharp(ctx, targets, args):
    item = ctx.item(targets[0])
    _, chosen = pick(ctx, item, args["edges"], "edges")
    have = set(mesh_book.crease_pairs(item))
    have = have | chosen if args.get("sharp", True) else have - chosen
    ctx.set(targets[0], "creases", mesh_book.flat(have))
    return {"edges": args["edges"]}
