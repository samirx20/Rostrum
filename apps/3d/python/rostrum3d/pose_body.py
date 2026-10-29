"""A posed clay figure as balls, for the pose checks (pose_faults.py): each added piece of the clay (a sphere's middle,
points along a capsule, a drawn or spun piece's balls, mirrored pieces on both sides) as a ball in the clay's own space,
given to the bone that bends the surface there (follow.nearest_bone: the core's weights, a clay's pieces), and carried
through that bone's move (follow.bone_move: now times rest) and the clay's world transform at a frame. Nothing is built
or rendered; a piece of the surface is where its bone takes it, which is what the core draws there to within a blend.
"""
from __future__ import annotations

import math

from . import aim, clay_shapes, follow, skin, skin_parts

STEP = 0.75                 # points along a capsule: one every STEP × its radius


def _ends(s: dict) -> list:
    """(point, radius) balls of one added piece, in the clay's own space."""
    if s.get("plane"):
        return [([float(v) for v in p], float(r)) for p, r in clay_shapes.balls(s)]
    r, a = float(s.get("radius", 0.1)), [float(v) for v in s["at"]]
    if s.get("shape") != "capsule" or not s.get("to"):
        return [(a, r)]
    b = [float(v) for v in s["to"]]
    n = max(1, math.ceil(math.dist(a, b) / (STEP * r)))
    return [([a[k] + (b[k] - a[k]) * i / n for k in range(3)], r) for i in range(n + 1)]


def rest_balls(item: dict) -> list[tuple[list[float], float, int]]:
    """[(point, radius, bone index in skin.bones_of's order)] of a clay with bones, at rest in its own space; [] without."""
    if not skin.bones_of(item) or not item.get("skinned", True):
        return []
    out = []
    for s in item.get("steps", []):
        if s.get("step") != "piece" or s.get("hidden") or s.get("mode", "add") != "add" or not (s.get("at") or s.get("plane")):
            continue
        own = _ends(s)
        if s.get("symmetry") == "x":
            own += [([-p[0], p[1], p[2]], r) for p, r in own if abs(p[0]) > 1e-9]
        out += [(p, r) for p, r in own]
    return [(p, r, b) for (p, r), b in zip(out, _bones(item, [p for p, _ in out]))]


def _bones(item: dict, points: list) -> list[int]:
    """The bone each point bends with: the nearest bone segment of the clay's piece the point is in (skin_parts' cells),
    without spreading the shares (follow.nearest_bone's exact rule costs seconds; this costs milliseconds)."""
    chain = skin.bones_of(item)
    rest = skin.transforms(chain)
    segs = [skin.segment(m, b) for m, (b, _) in zip(rest, chain)]
    parts = skin_parts.for_core(item["jointParts"], chain, segs) if item.get("jointParts") else None
    cells = skin_parts._cells(parts) if parts else None
    out = []
    for p in points:
        piece = skin_parts.piece_near(parts, cells, p) if parts else -1
        own = [n for n, b in enumerate(parts["bone"]) if b == piece] if parts else []
        out.append(min(own or range(len(segs)), key=lambda n: _seg_dist(p, segs[n])))
    return out


def _seg_dist(p, seg) -> float:
    a, b = seg[:3], seg[3:]
    ab = [y - x for x, y in zip(a, b)]
    t = sum((q - x) * c for q, x, c in zip(p, a, ab)) / (sum(c * c for c in ab) or 1e-30)
    return math.dist(p, [x + max(0.0, min(1.0, t)) * c for x, c in zip(a, ab)])


def scale_of(m) -> float:
    return max(sum(row[k] ** 2 for row in m[0]) ** 0.5 for k in range(3))


def posed(fr, id_: str, balls: list, f: int) -> list[tuple[list[float], float, int]]:
    """The balls in the world at frame f, each carried by its bone's move then the clay's transform."""
    world = fr.world(id_, f)
    s = scale_of(world)
    return [(aim.point(world, aim.point(follow.bone_move(fr, id_, b, f), p)), r * s, b) for p, r, b in balls]


def joint_names(item: dict) -> list[str]:
    return [b.get("joint") or b.get("name") or b["id"] for b, _ in skin.bones_of(item)]


def parents(item: dict) -> list[int]:
    return [p for _, p in skin.bones_of(item)]


def surface_gap(balls: list, p) -> tuple[float, int]:
    """(distance from p to the nearest ball's surface, negative inside; that ball's bone)."""
    d, b = min(((math.dist(p, q) - r, b) for q, r, b in balls), key=lambda x: x[0])
    return d, b
