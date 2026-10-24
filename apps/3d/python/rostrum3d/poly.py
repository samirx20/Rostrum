"""An editable mesh's geometry (SPEC §4.3): points, and faces as lists of point indices, anticlockwise seen from
outside (USD's order). Pure functions on plain lists; ops_mesh.py turns them into one undo step each, the core draws
the result (preview ≡ export). Units are the item's own space, metres.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

Vec = list[float]


@dataclass
class Change:
    """What a topology edit made, for mesh_book.apply (the one place faceMaterials and creases follow edits):
    `parents[n]` is the old face new face n came from (-1: none, it gets the item's material); `chains` maps an old
    edge (a, b), a < b, that is gone to the points now along it from a to b (a cut edge's halves, a moved edge);
    `kept` is the faces to hand back as the selection."""
    points: list
    faces: list
    parents: list
    chains: dict = field(default_factory=dict)
    kept: set = field(default_factory=set)


def sub(a, b): return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
def add(a, b, k=1.0): return [a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k]
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def unit(v):
    n = math.sqrt(dot(v, v))
    return [x / n for x in v] if n > 1e-12 else [0.0, 0.0, 0.0]


def faces_of(item: dict) -> list[list[int]]:
    out, i = [], 0
    for n in item.get("faceCounts", []):
        out.append(list(item["faceIndices"][i:i + n]))
        i += n
    return out


def pack(points: list[Vec], faces: list[list[int]]) -> dict:
    """The item fields for this geometry."""
    return {"points": [[float(c) for c in p] for p in points], "faceCounts": [len(f) for f in faces],
            "faceIndices": [i for f in faces for i in f]}


def normal(points, face) -> Vec:
    """Newell's normal: right for any flat or nearly flat polygon, convex or not."""
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(face):
        p, q = points[a], points[face[(i + 1) % len(face)]]
        n = add(n, [(p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]), (p[0] - q[0]) * (p[1] + q[1])])
    return unit(n)


def centre(points, ids) -> Vec:
    ids = list(ids)
    c = [0.0, 0.0, 0.0]
    for i in ids:
        c = add(c, points[i])
    return [x / max(1, len(ids)) for x in c]


def weld(points, counts, indices, tol: float = 1e-6) -> tuple[list[Vec], list[list[int]]]:
    """The core's drawn mesh (one vertex per hard edge or seam) as one point per place: points closer than `tol`
    become one; corners repeated by that are dropped, and faces left with fewer than 3 go."""
    key = lambda p: tuple(round(c / tol) for c in p)  # noqa: E731
    where, out, remap = {}, [], []
    for p in points:
        k = key(p)
        if k not in where:
            where[k] = len(out)
            out.append([float(c) for c in p])
        remap.append(where[k])
    faces, i = [], 0
    for n in counts:
        f = []
        for v in (remap[j] for j in indices[i:i + n]):
            if not f or f[-1] != v:
                f.append(v)
        while len(f) > 1 and f[0] == f[-1]:
            f.pop()
        if len(set(f)) >= 3:
            faces.append(f)
        i += n
    used = sorted({v for f in faces for v in f})
    new = {v: n for n, v in enumerate(used)}
    return [out[v] for v in used], [[new[v] for v in f] for f in faces]


def extrude(points, faces, chosen: set[int], distance: float) -> Change:
    """Push the chosen faces out by `distance` along their normals, as one piece: points shared by chosen faces move
    together (each along the average normal of its chosen faces), and walls join the piece's border to where it was.
    The moved faces stay the selection; each wall takes the material of the face it grew from."""
    points = [list(p) for p in points]
    faces = [list(f) for f in faces]
    inside = {(f[i], f[(i + 1) % len(f)]): n for n in chosen for f in [faces[n]] for i in range(len(f))}
    border = [(a, b) for a, b in inside if (b, a) not in inside]
    parents = list(range(len(faces))) + [inside[e] for e in border]
    dirs: dict[int, Vec] = {}
    for n in chosen:
        nm = normal(points, faces[n])
        for v in faces[n]:
            dirs[v] = add(dirs.get(v, [0.0, 0.0, 0.0]), nm)
    moved = {}
    for v, d in dirs.items():
        moved[v] = len(points)
        points.append(add(points[v], unit(d), distance))
    for n in chosen:
        faces[n] = [moved[v] for v in faces[n]]
    for a, b in border:
        faces.append([a, b, moved[b], moved[a]])
    chains = {(min(a, b), max(a, b)): [moved[min(a, b)], moved[max(a, b)]] for a, b in inside}
    return Change(points, faces, parents, chains, set(chosen))


def inset(points, faces, chosen: set[int], width: float, depth: float, where: str = "") -> Change:
    """Each chosen face gets a smaller copy of itself `width` in from its edges (and `depth` out along its normal),
    joined to its old outline by a ring of faces. The copies stay chosen."""
    points = [list(p) for p in points]
    faces = [list(f) for f in faces]
    parents = list(range(len(faces)))
    for n in sorted(chosen):
        f = faces[n]
        nm, c = normal(points, f), centre(points, f)
        room = min(abs(dot(sub(c, points[a]), unit(cross(nm, sub(points[b], points[a])))))
                   for a, b in zip(f, f[1:] + f[:1]))
        if width >= room:
            raise ValueError(f"{where}width {width:g} m is too wide for face {n}: at most {room:g} m fits")
        inner = []
        for i, v in enumerate(f):
            prev, nxt = points[f[i - 1]], points[f[(i + 1) % len(f)]]
            in1 = unit(cross(nm, sub(points[v], prev)))
            in2 = unit(cross(nm, sub(nxt, points[v])))
            k = 1.0 + dot(in1, in2)
            off = [x * width / k for x in add(in1, in2)] if k > 1e-6 else in1
            inner.append(len(points))
            points.append(add(add(points[v], off), nm, depth))
        for i in range(len(f)):
            j = (i + 1) % len(f)
            faces.append([f[i], f[j], inner[j], inner[i]])
            parents.append(n)
        faces[n] = inner
    return Change(points, faces, parents, {}, set(chosen))


def turn_matrix(deg: Vec) -> list[Vec]:
    """Rows of the X-then-Y-then-Z turn (the items' rotateXYZ order), for column vectors: R = Rz · Ry · Rx."""
    rx, ry, rz = (math.radians(d) for d in deg)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    return [[cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
            [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
            [-sy, cy * sx, cy * cx]]


def transform(points, ids: set[int], move=(0, 0, 0), turn=(0, 0, 0), scale=(1, 1, 1), around=None) -> list[Vec]:
    """Scale, then turn, around `around` (default: the points' middle), then move: the chosen points only."""
    points = [list(p) for p in points]
    c = list(around) if around is not None else centre(points, ids)
    m = turn_matrix(list(turn))
    for i in ids:
        d = [(points[i][k] - c[k]) * scale[k] for k in range(3)]
        points[i] = [c[k] + dot(m[k], d) + move[k] for k in range(3)]
    return points
