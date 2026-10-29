"""Automatic unfolding (SPEC §5): `mesh.unfold` lays a mesh's surface flat into its square paint picture, so it can be
painted. The core does it (xatlas, the `unfold` request, ENGINE_CONTRACT.md § 1) on the mesh exactly as it draws it;
the answer is stored as data on the item (`uvs`, one (u, v) per face corner): analysed once, stored, never redone
by a render. One operation, one undo step. The built mesh those corners belong to is kept in the shared cache beside
it (paint_masks.keep_geometry), for the automatic masks (Edges, Facing up …).

Like mesh.edit it needs the engine: the app and the MCP server hand theirs over through ops_mesh.use_engine; without
one it fails loudly. A shape changed after unfolding no longer matches its `uvs` and the core says so: unfold again.
"""
from __future__ import annotations

from rostrum_core.errors import codes

from . import compile as C
from .kind import REGISTRY as R

_UNFOLD = None       # (doc, item id, size) -> the core's unfold reply


def use_engine(engine, folder=None):
    """Let mesh.unfold ask this engine (through the document's first shot's scene, the item's old uvs left out)."""
    global _UNFOLD

    def unfold(doc: dict, id_: str, size: int) -> dict:
        shots = doc.get("shots") or []
        if not shots:
            raise ValueError("the document has no shot yet, so the engine can't build the scene (shot.add first)")
        scene = C.describe(doc, shots[0]["id"], folder)
        _drop_uvs(scene["items"], id_)               # unfold the shape as made, whatever it was unfolded to before
        engine.ensure_scene(scene)
        reply = engine.unfold(id_, size)
        # the built mesh those corners belong to, kept for the paint layers' automatic masks (paint_masks.py)
        return {**reply, "geometry": engine.geometry(id_)}
    _UNFOLD = unfold if engine is not None else None


def use_unfold(fn):
    """Tests: any (doc, id, size) -> {"uvs": […], "geometry"?: {points, faceCounts, faceIndices}} function."""
    global _UNFOLD
    _UNFOLD = fn


def _drop_uvs(nodes: list, id_: str) -> bool:
    for n in nodes:
        if n["id"] == id_:
            n["props"]["uvs"] = []
            return True
        if _drop_uvs(n.get("children", []), id_):
            return True
    return False


@R.operation("mesh.unfold", "Lay the mesh's surface flat into its paint picture (paintSize, 2048 px unless set), cut "
             "into a few pieces where it must (xatlas), so it can be painted; stored on the mesh as `uvs`. Paint mode "
             "and paint.add do it by themselves for a mesh that has none. Again after changing the shape. One undo step.",
             target="mesh", label="Unfold", importance="secondary")
def mesh_unfold(ctx, targets, args):
    if _UNFOLD is None:
        ctx.fail(codes.BAD_ARGUMENT, "mesh.unfold", "has no engine to unfold with",
                 hint="Run it in the app or through the 3D MCP server (they start the engine).")
    out = {}
    for t in targets:
        size = ctx.item(t).get("paintSize", 2048)
        try:
            reply = _UNFOLD(ctx.doc, t, size)
        except Exception as e:  # noqa: BLE001  any engine failure is this operation's, named
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f"could not be unfolded: {e}")
        ctx.set(t, "uvs", reply["uvs"])
        if reply.get("geometry"):
            from .paint_masks import keep_geometry
            keep_geometry(reply["uvs"], reply["geometry"])
        out[t] = {"pieces": reply.get("charts"), "covered": reply.get("used"), "split faces": reply.get("split")}
    return {"unfolded": out}


def _unfolding(fn):
    """paint.add on a mesh never unfolded unfolds it first, in the same change (as Paint mode does on the screen):
    a primitive's own surface coordinates are not a paint picture (a box's top and bottom share its walls' square and a
    thin wall is stretched over the whole height), so paint laid on them shows in the wrong places. Without an engine
    (a bare document) it is left as it was."""
    def paint_add(ctx, targets, args):
        if _UNFOLD is not None:
            todo = [t for t in targets or [] if ctx.item(t).get("type") == "mesh" and not ctx.item(t).get("uvs")]
            if todo:
                mesh_unfold(ctx, todo, {})
        return fn(ctx, targets, args)
    return paint_add


for _op in R.ops():
    if _op.name == "paint.add":
        _op.fn = _unfolding(_op.fn)
