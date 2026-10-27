"""Standing a mesh on a surface at a point (Place on a surface, SPEC §4.1): along the surface's direction there
(`normal`), its base on the surface. One place for the screen (app/screen3d/placing.py, after the engine's pick), the
agents' `edit_place_on` and the script's `place_on(…, at=)`; and whether that point is on a mirrored clay, so the part
gets its mirrored copy (mirror.py). Plain maths.
"""
from __future__ import annotations

import math

from . import aim
from .shape_size import half_height

STRAIGHT = 0.01                      # a surface direction this close to an axis is taken as the axis (smooth-shading noise)
ON_THE_MIRROR = 0.5                  # a part this close to the mirror (× its own size) sits across it: no copy


def clean(normal) -> list[float]:
    """`normal` with near-zero parts made zero, unit length: a box's top gives exactly up, so nothing is tilted 0.04°."""
    n = [0.0 if abs(c) < STRAIGHT else c for c in normal]
    length = math.hypot(*n) or 1.0
    return [c / length for c in n]


def up_turn(normal) -> tuple[float, float]:
    """(rx, rz) degrees that stand the shape's up (+Y) along `normal` (X turn first, then Z: aim.py's order)."""
    nx, ny, nz = normal
    rx = math.degrees(math.asin(max(-1.0, min(1.0, nz))))
    rz = math.degrees(math.atan2(-nx, ny)) if math.hypot(nx, ny) > 1e-9 else 0.0
    return rx, rz


def stand(values: dict, point, normal) -> dict:
    """The x y z (rx rz) in world space that stand a mesh with these shape fields on the surface at `point`."""
    normal = clean(normal)
    rx, rz = up_turn(normal)
    lift = half_height(values)
    x, y, z = (round(p + n * lift, 4) for p, n in zip(point, normal))     # to a tenth of a millimetre
    return {"x": x, "y": y, "z": z, **({"rx": round(rx, 4)} if abs(rx) > 1e-4 else {}),
            **({"rz": round(rz, 4)} if abs(rz) > 1e-4 else {})}


def into_parent(args: dict, parent_world) -> dict:
    """`args`' world position and turn moved into a parent's space (a new item going into a group or combine)."""
    if parent_world is aim.IDENTITY:
        return args
    inv = aim._inverse(parent_world[0])
    p = aim._apply(inv, [a - t for a, t in zip((args["x"], args["y"], args["z"]), parent_world[1])])
    turn = aim._mul(inv, aim.local({"x": 0, "y": 0, "z": 0, "rx": args.get("rx", 0.0), "ry": args.get("ry", 0.0),
                                    "rz": args.get("rz", 0.0), "sx": 1, "sy": 1, "sz": 1})[0])
    rx, ry, rz = aim.euler(turn)
    return {**args, "x": p[0], "y": p[1], "z": p[2], "rx": rx, "ry": ry, "rz": rz}


def mirrors(clay: dict | None, clay_world, point, size: float) -> bool:
    """Whether a part of `size` put at world `point` on `clay` gets a mirrored copy: the clay's Mirror is on and the
    point is off its mirror (on it, the part sits across the middle: a nose, not an eye)."""
    if not clay or clay.get("type") != "clay" or clay.get("symmetry", "x") != "x":
        return False
    local = aim.point(aim.invert(clay_world), list(point))
    scale = math.hypot(*(clay_world[0][r][0] for r in range(3))) or 1.0
    return abs(local[0]) * scale > ON_THE_MIRROR * size
