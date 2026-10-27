"""Editable mesh operations (SPEC §4.3, part 1): make a shape or a combine editable (`mesh.edit`), then extrude and
inset faces and move, turn or scale points, edges and faces. Each is one operation, so one undo step; what to change
is named by a selector (mesh_select.py). The geometry maths is poly.py; the core draws the result.

`mesh.edit` needs the shape as the core makes it (one source of truth for every shape and for Manifold's combines):
the app and the MCP server hand it their engine with `use_engine`; without one it fails loudly.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import build, compile as C, fields as F, mesh_book, mesh_select as MS, poly
from .kind import REGISTRY as R

_GEOMETRY = None          # (doc, item id) -> {"points", "faceCounts", "faceIndices"} as the core drew it


def use_engine(engine, folder=None):
    """Let mesh.edit (and mesh.unfold) ask this engine for a shape's mesh (through the document's first shot's scene)."""
    global _GEOMETRY

    def geometry(doc: dict, id_: str) -> dict:
        shots = doc.get("shots") or []
        if not shots:
            raise ValueError("the document has no shot yet, so the engine can't build the scene (shot.add first)")
        engine.ensure_scene(C.describe(doc, shots[0]["id"], folder))
        return engine.geometry(id_)
    _GEOMETRY = geometry if engine is not None else None
    from . import ops_import, ops_pose, unfold
    ops_import.use_engine(engine)                    # import.add reads a file's units, size and parts through it
    unfold.use_engine(engine, folder)                # mesh.unfold asks the same engine
    ops_pose.use_engine(engine, folder)              # pose.find_joints asks it for the clay's grid


def use_geometry(fn):
    """Tests: any (doc, id) -> raw mesh function."""
    global _GEOMETRY
    _GEOMETRY = fn


SELECT = Param.text("select", label="Selection", required=True,
                    help="Which points, edges or faces: " + " · ".join(f'"{f}"' for f in MS.FORMS))
FACES = Param.text("faces", label="Faces", required=True, help='Which faces: "top", "faces 3 4", "faces facing +y" …')
THREE = lambda name, label, default, help: Param.list(name, "number", label=label, min=-1e5, max=1e5, min_items=3,  # noqa: E731
                                                      max_items=3, default=default, help=help)
EDITABLE = F.POLY
TRANSFORM_KEYS = [p.name for p in F.TRANSFORM]


def pick(ctx, item, selector, want=None):
    try:
        kind, chosen = MS.parse(selector, item)
    except MS.BadSelector as e:
        ctx.fail(codes.BAD_ARGUMENT, f'"{selector}"', str(e).split(". Accepted")[0].split('" ', 1)[-1], MS.FORMS)
    if want and kind != want:
        ctx.fail(codes.BAD_ARGUMENT, f'"{selector}"', f"picks {kind}; this needs {want}", MS.FORMS)
    if not chosen:
        ctx.fail(codes.BAD_ARGUMENT, f'"{selector}"', "picks nothing on this mesh",
                 hint='Check it first: look_frame shows the mesh; "all" picks every face.')
    return kind, chosen


def _store(ctx, id_, points, faces):
    for k, v in poly.pack(points, faces).items():
        ctx.set(id_, k, v)


def store_change(ctx, id_, change: poly.Change) -> str:
    """Set a topology edit's result (faceMaterials and creases follow it, mesh_book.py); its faces' selector."""
    try:
        fields = mesh_book.apply(ctx.item(id_), change)
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, f'target "{id_}"', str(e),
                 hint="Set faceMaterials to [] with mesh.set, then retry.")
    for k, v in fields.items():
        ctx.set(id_, k, v)
    return MS.text("faces", change.kept)


@R.operation("mesh.edit", "Turn a shape (box, sphere, text …) or a combine into an editable mesh: its points and "
             "faces exactly as drawn, welded where they meet. Keeps the name, place, material and keys; a combine's "
             "inputs are gone afterwards (this is the combine's Bake). One undo step.",
             target=("mesh", "combine"), label="Edit mesh", valid_when={"not": EDITABLE})
def mesh_edit(ctx, targets, args):
    if _GEOMETRY is None:
        ctx.fail(codes.BAD_ARGUMENT, "mesh.edit", "has no engine to read the shape from",
                 hint="Run it in the app or through the 3D MCP server (they start the engine).")
    out = []
    for t in targets:
        try:
            raw = _GEOMETRY(ctx.doc, t)
        except Exception as e:  # noqa: BLE001  any engine failure is this operation's, named
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f"could not be read from the engine: {e}")
        points, faces = poly.weld(raw["points"], raw["faceCounts"], raw["faceIndices"])
        item = ctx.item(t)
        if item["type"] == "mesh":
            ctx.set(t, "shape", "poly")
            _store(ctx, t, points, faces)
            ctx.set(t, "faceMaterials", [])
            ctx.set(t, "creases", [])
            out.append(t)
            continue
        loc = index(ctx.doc, ctx.kind.lists)[t]
        mesh = build.make("mesh", t, {"name": item.get("name") or t, "material": item.get("material", ""),
                                      "shape": "poly", **poly.pack(points, faces)}, ctx.where)
        mesh.update({k: item[k] for k in TRANSFORM_KEYS if k in item})     # already checked values, aim fields too
        mesh["keys"] = list(item.get("keys", []))
        ctx.remove(t)
        ctx.insert(loc.parent, loc.key, mesh, loc.index)
        out.append(t)
    return {"edited": out}


@R.operation("faces.extrude", "Push faces out along their normals by `distance` (negative pushes in), as one piece, "
             "with new side walls joining them to where they were. The pushed faces stay the selection.",
             target="mesh", label="Extrude", valid_when=EDITABLE,
             params=[FACES, Param.number("distance", label="Distance", min=-1e3, max=1e3, step=0.0005, unit="m",
                                         default=0.002, help="How far out (negative: in)")])
def faces_extrude(ctx, targets, args):
    item = ctx.item(targets[0])
    _, chosen = pick(ctx, item, args["faces"], "faces")
    change = poly.extrude(item["points"], poly.faces_of(item), chosen, args.get("distance", 0.002))
    return {"faces": store_change(ctx, targets[0], change)}


@R.operation("faces.inset", "Make a smaller copy of each face `width` in from its edges (and `depth` out along it), "
             "joined to the old outline by a ring of faces; the copies stay the selection (extrude them next for a "
             "raised or sunken panel).", target="mesh", label="Inset", valid_when=EDITABLE,
             params=[FACES, Param.number("width", label="Width", min=0, max=1e3, step=0.0005, unit="m", default=0.002),
                     Param.number("depth", label="Depth", min=-1e3, max=1e3, step=0.0005, unit="m", default=0.0,
                                  help="Out along the face (negative: in)")])
def faces_inset(ctx, targets, args):
    item = ctx.item(targets[0])
    _, chosen = pick(ctx, item, args["faces"], "faces")
    try:
        change = poly.inset(item["points"], poly.faces_of(item), chosen, args.get("width", 0.002),
                            args.get("depth", 0.0))
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, '"width"', str(e), hint="Use a smaller width.")
    return {"faces": store_change(ctx, targets[0], change)}


@R.operation("mesh.transform", "Move, turn or scale points, edges or faces of an editable mesh, in its own space: "
             "scale, then turn (degrees, X then Y then Z), around the selection's middle, then move (metres).",
             target="mesh", label="Move points", valid_when=EDITABLE,
             params=[SELECT, THREE("move", "Move", [0.0, 0.0, 0.0], "[x, y, z] metres"),
                     THREE("turn", "Turn", [0.0, 0.0, 0.0], "[x, y, z] degrees"),
                     THREE("scale", "Scale", [1.0, 1.0, 1.0], "[x, y, z] times")])
def mesh_transform(ctx, targets, args):
    item = ctx.item(targets[0])
    kind, chosen = pick(ctx, item, args["select"])
    ids = MS.points_in(item, kind, chosen)
    pts = poly.transform(item["points"], ids, args.get("move", [0, 0, 0]), args.get("turn", [0, 0, 0]),
                         args.get("scale", [1, 1, 1]))
    ctx.set(targets[0], "points", pts)
    return {"select": MS.text(kind, chosen)}
