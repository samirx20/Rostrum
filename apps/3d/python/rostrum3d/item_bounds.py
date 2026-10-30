"""How much room items take in the world, as one box (lowest and highest x y z), for framing them (`shot.frame`).

A shape of fixed form (box, sphere, cylinder, cone, capsule, plane, disc, torus) is measured from its fields; an
editable mesh, an outline (text, logo, drawing) or a combine asks the engine for its built mesh (the same hook
mesh.edit uses: ops_mesh.use_engine); a clay is the points its pieces reach (clay_detail.reach); a light or a camera
is its place; a group or a rig is everything in it; a copies item is what its copies take as the engine draws them then
(laid out, held, keyed or fallen: the core's `copies_box`); an import is the bounds the engine reads in its file (its
prim, or the file's default prim; the engine's inspect_usd, the same read import.add lands it by), in the file's own
numbers, carried by the import's scale and turn. Each box goes through the item's world transform at the time asked,
so a moving item is framed where it is then.
"""
from __future__ import annotations

import os

from . import aim, clay_detail
from .resolve import Frames

POINTS = ("light", "camera")
HOLDERS = ("group", "rig")
MEASURED = ("group", "rig", "mesh", "combine", "clay", "copies", "import", "light", "camera")   # what world_box can measure

_FILES: dict = {}          # file -> ((file, mtime, size), the engine's inspect_usd answer)
_COPIES = None            # (doc, copies id, t seconds) -> (lo, hi) world, or None when it has no copies (use_engine)


def use_engine(engine, folder=None):
    """Let framing ask this engine where a copies item's copies are (through the document's first shot's scene)."""
    global _COPIES
    if engine is None:
        _COPIES = None
        return

    def box(doc: dict, id_: str, t: float):
        from . import compile as C
        shots = doc.get("shots") or []
        if not shots:
            raise ValueError("the document has no shot yet, so the engine can't build the scene (shot.add first)")
        engine.ensure_scene(C.describe(doc, shots[0]["id"], folder))
        info = C.shot_info(doc, shots[0]["id"])
        frame = min(max(round(t * info["fps"]), info["start"]), info["end"])
        out = engine.copies_box(id_, frame)
        return (out["lo"], out["hi"]) if out.get("lo") is not None else None
    _COPIES = box


def use_copies_box(fn):
    """Tests: any (doc, id, t) -> (lo, hi) | None function."""
    global _COPIES
    _COPIES = fn


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


def _import_box(item: dict):
    """(lo, hi) of an import in its own space (the file's numbers; the item's sx/rx carry its unit rescale and Z-up turn)."""
    from . import ops_import
    if ops_import._INSPECT is None:
        raise ValueError(f'"{item["id"]}" is measured from its file, which the engine reads, and no engine is running here')
    try:
        st = os.stat(item["file"])
        stamp = (item["file"], st.st_mtime_ns, st.st_size)
    except OSError:
        stamp = None                         # the engine says what is wrong with the path
    if stamp is None or _FILES.get(item["file"], (None,))[0] != stamp:   # a framed push-in measures it once
        _FILES[item["file"]] = (stamp, ops_import._INSPECT(item["file"]))
    box = ops_import.file_bounds(_FILES[item["file"]][1], item.get("prim", ""))
    if box is None:
        raise ValueError(f'"{item["id"]}": nothing in {item["file"]} {item.get("prim") or "(its default prim)"} has a size')
    return box


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
    if kind == "clay":                       # its pieces' own reach, not a box's corners: framed snugly from any side
        return [aim.point(world, p) for p in clay_detail.reach(item)]
    if kind == "copies":                     # the engine lays copies out: its box is world already
        if _COPIES is None:
            raise ValueError(f'"{id_}" is measured from the copies the engine lays out, and no engine is running here')
        box = _COPIES(doc, id_, f / fr.fps)
        return _corners(*box) if box else []
    elif kind == "mesh":
        box = _shape_box(fr.values(id_, f)) or _built(doc, id_)
    elif kind == "combine":
        box = _built(doc, id_)
    elif kind == "import":
        box = _import_box(item)
    else:
        raise ValueError(f'"{id_}" is a {kind}: its size isn\'t known here, so it can\'t be framed')
    return [aim.point(world, c) for c in _corners(*box)] if box else []


SHAPES = ("mesh", "combine", "clay")


def solid(doc: dict, fr: Frames, id_: str, f: int, built: dict):
    """(corners, axes) of one shape item at frame f, for overlap tests: a mesh or combine's own box carried into the world
    (an oriented box: its 8 corners and its 3 edge directions), a clay's reach as a world-aligned box; None when it has no
    shape yet (an empty clay or mesh). `built` keeps the engine-built boxes asked once per item. ValueError for an item
    that is not a shape (SHAPES)."""
    kind = fr.items[id_]["type"]
    if kind not in SHAPES:
        raise ValueError(f'"{id_}" is a {kind}: only {", ".join(SHAPES)} have a shape to measure here')
    if kind == "clay":
        pts = _own_points(doc, fr, id_, f)
        if not pts:
            return None
        lo, hi = [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]
        return _corners(lo, hi), aim.IDENTITY[0]
    v = fr.values(id_, f) if kind == "mesh" else {}
    box = _shape_box(v) if kind == "mesh" else None
    if box is None:
        box = built[id_] if id_ in built else built.setdefault(id_, _built(doc, id_))
    if not box:
        return None
    world = fr.world(id_, f)
    if v.get("shape") == "sphere":     # a ball's box does not turn with it: a rolled ball's turned box reached ~3.5 cm
        c = aim.point(world, [0.0, 0.0, 0.0])        # below it, so a ball at rest on a box "passed through" it (sweep fix)
        r = v["radius"] * max(sum(row[k] ** 2 for row in world[0]) ** 0.5 for k in range(3))
        return _corners([x - r for x in c], [x + r for x in c]), aim.IDENTITY[0]
    return [aim.point(world, c) for c in _corners(*box)], [[row[k] for row in world[0]] for k in range(3)]


def world_box(doc: dict, ids: list[str], t: float = 0.0):
    """(lo, hi) of everything in `ids` at `t` seconds; ValueError when there is nothing to measure."""
    f = round(t * 1000)
    fr = Frames(doc, range(f, f + 1), 1000.0)
    pts = [p for i in ids for p in _own_points(doc, fr, i, f)]
    if not pts:
        raise ValueError("there is nothing in it to frame (an empty group or clay)")
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]
