"""Simple bone chains (SPEC §9): `bone.chain` lays a chain of bones along points on a mesh (a strap, a cable, a tail)
and binds the mesh to it, in one step; `bone.bind` turns the bending off or on again. A chain is nested items, each
bone inside the one before it: mesh › bone 1 › bone 2 › bone 3 (the mesh's `bones` list, then each bone's own). The
person (and an agent) then poses the chain only by keying each bone's Turn (`key.add` rx / ry / rz, poses too);
the compiler sends the bends to the core as the mesh's `skin` (skin.py), which weights the points itself.

Each bone is aimed at the next point: its own +Y runs from its head to the next point (skin.py's convention), turned
from the bone before it by the smallest turn that does it, so a straight chain has no twist along it.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes

from . import aim, build, resolve
from .kind import REGISTRY as R

POINTS = Param.points("points", label="Points", required=True, min=3, max=3, unit="m",
                      help="Two or more [x, y, z] along the mesh, in order (root first): each pair makes a bone. "
                           "World positions at time 0 (where a click lands), or the mesh's own space with space=mesh")
SPACE = Param.choice("space", ["world", "mesh"], label="Points in", default="world", importance="deep",
                     help="world: scene positions at time 0 (default). mesh: the mesh's own space, before its "
                          "position, turn and scale (its middle is 0 0 0)")
OFF = Param.toggle("off", label="Stop bending", importance="secondary",
                   help="The mesh keeps its shape; its bones and their keys stay")
SHORTEST = 1e-4                                   # metres: two points closer than this can't make a bone


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def _arc(a, b):
    """The smallest turn (3×3) taking unit direction a onto unit direction b (Rodrigues)."""
    axis = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    s, c = math.sqrt(sum(x * x for x in axis)), sum(x * y for x, y in zip(a, b))
    if s < 1e-12:
        if c > 0:
            return [r[:] for r in aim.IDENTITY[0]]
        axis = _unit([1.0, 0.0, 0.0] if abs(a[0]) < 0.9 else [0.0, 0.0, 1.0])
        axis = _unit([axis[1] * a[2] - axis[2] * a[1], axis[2] * a[0] - axis[0] * a[2], axis[0] * a[1] - axis[1] * a[0]])
        s, c = 0.0, -1.0
    else:
        axis = [x / s for x in axis]
    k, (x, y, z) = 1 - c, axis
    return [[c + x * x * k, x * y * k - z * s, x * z * k + y * s],
            [y * x * k + z * s, c + y * y * k, y * z * k - x * s],
            [z * x * k - y * s, z * y * k + x * s, c + z * z * k]]


def _t(m):
    return [list(r) for r in zip(*m)]


def rest_chain(points: list[list[float]]) -> list[dict]:
    """Each bone's x y z rx ry rz length (in its parent's space) for a chain through `points` (the mesh's own space)."""
    out, turn = [], aim.IDENTITY[0]
    for i, (a, b) in enumerate(zip(points, points[1:])):
        d = _sub(b, a)
        length = math.sqrt(sum(x * x for x in d))
        if length < SHORTEST:
            raise ValueError(f"points {i} and {i + 1} are at the same place; each bone needs two different points")
        new = aim._mul(_arc(_unit([turn[r][1] for r in range(3)]), _unit(d)), turn)   # parallel: no twist along
        rx, ry, rz = aim.euler(aim._mul(_t(turn), new))
        head = a if i == 0 else [0.0, out[-1]["length"], 0.0]
        out.append({"x": head[0], "y": head[1], "z": head[2], "rx": rx, "ry": ry, "rz": rz, "length": length})
        turn = new
    return [{k: round(v, 6) + 0.0 for k, v in b.items()} for b in out]      # + 0.0: never a −0


def _bone_id(ctx, mesh: str, n: int) -> str:
    want = f"{mesh}_bone{n}"
    return ctx.new_id("bone") if ctx.idx.get(want) else want


@R.operation("bone.chain", "Lay a chain of bones along points on a mesh (a strap, a cable, a tail) and bind the mesh "
             "to it, in one step: len(points) − 1 bones, root first, each from one point to the next and nested in "
             "the one before (mesh › bone1 › bone2 …), ids <mesh>_bone1, _bone2 …. A chain the mesh already has is "
             "replaced. Then bend it by keying each bone's Turn (key.add prop rx / ry / rz, `v` in degrees, the rest "
             "turn plus the bend); the mesh bends with them in the viewport and the render. A bone's +Y runs along it. "
             "The mesh needs segments along its length to bend smoothly (a poly mesh, or a capsule / cylinder).",
             target="mesh", label="Make bone chain", params=[POINTS, SPACE])
def bone_chain(ctx, targets, args):
    pts = args["points"]
    if len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "targets", f"name {len(targets)} meshes; a chain goes on one mesh")
    if len(pts) < 2:
        ctx.fail(codes.BAD_ARGUMENT, "points", f"has {len(pts)}; a chain needs two or more (one bone per pair)")
    mesh = targets[0]
    if args.get("space", "world") == "world":
        back = aim.invert(resolve.world_at_start(ctx.doc, mesh))
        pts = [aim.point(back, p) for p in pts]
    try:
        bones = rest_chain([[float(x) for x in p[:3]] for p in pts])
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, "points", str(e))
    for old in list(ctx.item(mesh).get("bones", [])):
        ctx.remove(old["id"])
    made, parent = [], mesh
    for n, values in enumerate(bones, 1):
        made.append(_bone_id(ctx, mesh, n))
        ctx.insert(parent, "bones", build.make("bone", made[-1], {"name": f"Bone {n}", **values}, ctx.where))
        parent = made[-1]
    ctx.set(mesh, "skinned", True)
    return {"bones": made}


@R.operation("bone.bind", "Bend a mesh with its bone chain again, or (off) stop: it keeps its shape while its bones "
             "and their keys stay. The same as the mesh's Bend with bones.", target="mesh", label="Bend with bones",
             params=[OFF], valid_when={"fact": "boned"})
def bone_bind(ctx, targets, args):
    for t in targets:
        if not ctx.item(t).get("bones"):
            ctx.fail(codes.BAD_ARGUMENT, t, "has no bones (bone.chain lays some)")
        ctx.set(t, "skinned", not args.get("off", False))
