"""How much room items take in the world, as one box (lowest and highest x y z), for framing them (`shot.frame`).

A shape of fixed form (box, sphere, cylinder, cone, capsule, plane, disc, torus) is measured from its fields; an
editable mesh, an outline (text, logo, drawing) or a combine asks the engine for its built mesh (the same hook
mesh.edit uses: ops_mesh.use_engine); a clay is the sphere round its pieces (clay_detail.bounds); a light or a camera
is its place; a group or a rig is everything in it. Each box goes through the item's world transform at the time asked,
so a moving item is framed where it is then. An imported file has no size the Python side knows: refused loudly.
"""
from __future__ import annotations

from . import aim, clay_detail
from .resolve import Frames

POINTS = ("light", "camera")
HOLDERS = ("group", "rig")


def _shape_box(v: dict):
    """(lo, hi) of a fixed-form shape in its own space (centred on its origin, up +Y); None for any other shape."""
    s = v.get("shape")
    if s == "box":
        h = [v["width"] / 2, v["height"] / 2, v["depth"] / 2]
    elif s == "sphere":
        h = [v["radius"]] * 3
    elif s in ("cylinder", "cone", "capsule"):
        h = [v["radius"], v["height"] / 2, v["radius"]]
    elif s == "plane":
        h = [v["width"] / 2, 0.0, v["depth"] / 2]
    elif s == "disc":
        h = [v["radius"], 0.0, v["radius"]]
    elif s == "torus":
        h = [v["radius"] + v["tube"], v["tube"], v["radius"] + v["tube"]]
    else:
        return None
    return [-x for x in h], h


def _corners(lo, hi):
    return [[(lo, hi)[i >> k & 1][k] for k in range(3)] for i in range(8)]


def _built(doc: dict, id_: str):
    from . import ops_mesh
    if ops_mesh._GEOMETRY is None:
        raise ValueError(f'"{id_}" is measured from the mesh the engine builds, and no engine is running here')
    pts = ops_mesh._GEOMETRY(doc, id_)["points"]
    pts = [pts[i:i + 3] for i in range(0, len(pts), 3)] if pts and not isinstance(pts[0], list) else pts
    if not pts:
        return None
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]


def _own_points(doc: dict, fr: Frames, id_: str, f: int) -> list[list[float]]:
    """World points that hold the item (its box's corners, or its place); [] for an empty clay or group."""
    item, world = fr.items[id_], fr.world(id_, f)
    kind = item["type"]
    if kind in HOLDERS:
        return [p for c in item.get("children", []) for p in _own_points(doc, fr, c["id"], f)]
    if kind in POINTS:
        return [aim.point(world, [0.0, 0.0, 0.0])]
    if kind == "clay":
        ball = clay_detail.bounds(item)
        box = ([c - ball[1] for c in ball[0]], [c + ball[1] for c in ball[0]]) if ball else None
    elif kind == "mesh":
        box = _shape_box(fr.values(id_, f)) or _built(doc, id_)
    elif kind == "combine":
        box = _built(doc, id_)
    else:
        raise ValueError(f'"{id_}" is a {kind}: its size isn\'t known here, so it can\'t be framed')
    return [aim.point(world, c) for c in _corners(*box)] if box else []


def world_box(doc: dict, ids: list[str], t: float = 0.0):
    """(lo, hi) of everything in `ids` at `t` seconds; ValueError when there is nothing to measure."""
    f = round(t * 1000)
    fr = Frames(doc, range(f, f + 1), 1000.0)
    pts = [p for i in ids for p in _own_points(doc, fr, i, f)]
    if not pts:
        raise ValueError("there is nothing in it to frame (an empty group or clay)")
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]
