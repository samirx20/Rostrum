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
    """Whether a part `size` across put at world `point` on `clay` gets a mirrored copy: the clay's Mirror is on and the
    point is farther from its mirror than the part's own half size, so the two don't overlap (on the middle, the part
    sits across it: a nose, not an eye)."""
    if not clay or clay.get("type") != "clay" or clay.get("symmetry", "x") != "x":
        return False
    local = aim.point(aim.invert(clay_world), list(point))
    return abs(local[0]) * _scale(clay_world) > ON_THE_MIRROR * size


# ---- a part's size from the spot (SPEC §1 at 3:40: "a small ball sits on the face, sized for the face") ------------
SHARE = 0.16                         # a part on a clay: this share of the clay's width at the spot (an eye: ~1/6 face)
SMALLEST = 0.004                     # metres: never smaller than this


def _scale(world) -> float:
    return math.hypot(*(world[0][r][0] for r in range(3))) or 1.0


def _chord(poly, x: float, y: float) -> float | None:
    """The length of the piece of the horizontal line through (x, y) inside the closed 2-D outline, around x."""
    xs = sorted(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                for a, b in zip(poly, [*poly[1:], poly[0]]) if (a[1] > y) != (b[1] > y))
    return next((r - l for l, r in zip(xs[::2], xs[1::2]) if l <= x <= r), None)


def _width(step: dict, p) -> float | None:
    """How wide the step's own shape is at the clay-space point p (across, through p); None when p isn't in it."""
    shape = step.get("shape", "sphere")
    if shape in ("sphere", "capsule"):
        return 2 * float(step.get("radius", 0.1))
    pl = step.get("plane") or []
    if len(pl) != 9:
        return None
    o, u, v = pl[:3], pl[3:6], pl[6:]
    w = [a - b for a, b in zip(p, o)]
    x, y = sum(a * b for a, b in zip(w, u)), sum(a * b for a, b in zip(w, v))
    if shape == "outline" and len(step.get("outline") or []) >= 3:
        poly = step["outline"]
        found = [c for c in (_chord(poly, x, y), _chord([q[::-1] for q in poly], y, x)) if c]
        return min(found) if found else None
    if shape == "spin" and len(step.get("profile") or []) >= 2:
        r = math.sqrt(max(0.0, sum(c * c for c in w) - y * y))
        prof = step["profile"]
        c = _chord([[0.0, prof[0][1]], *prof, [0.0, prof[-1][1]]], min(r, 1e-6), y)
        return 2 * c if c else None
    return None


def part_size(clay: dict | None, clay_world, point) -> float | None:
    """How big (across, metres) a part placed at world `point` on `clay` is: SHARE of the clay's width there (the
    width of the drawn or spun shape, or the lump, that made that spot, across through it: a face's width on a
    head, a belly's on a body). None for anything else (the caller keeps its own size rule)."""
    if not clay or clay.get("type") != "clay":
        return None
    from . import step_find
    steps = [s for s in step_find.live(clay.get("steps", [])) if s.get("step") != "stroke" and s.get("mode") != "carve"]
    p = aim.point(aim.invert(clay_world), list(point))
    i, _ = step_find.owners(steps, [p])
    if i[0] < 0:
        return None
    step = steps[int(i[0])]
    width = _width(step, p) or (_width(step, [-p[0], p[1], p[2]]) if step.get("symmetry") == "x" else None)
    return max(SMALLEST, round(width * _scale(clay_world) * SHARE, 4)) if width else None
