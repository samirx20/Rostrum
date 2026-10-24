"""Placing a light by its highlight (SPEC §7, KeyShot's and HDR Light Studio's idea) and a light's starting brightness.

Place: a spot on a surface, seen from a camera, gets its highlight from where the view ray bounces to (the mirror of
the way the camera looks, about the surface's direction). The light goes there, `distance` away, aimed at the spot; a
sun instead shines straight onto the spot (its lit side). A strip stands upright (roll 90).

Starting brightness: `intensity` so the light gives the spot about `TARGET` of light (irradiance, in the scene's linear
units) whatever its size and distance: a panel's brightness times its area over the distance squared. A first try is
neither black nor blown out; Exposure then trims it by eye.

Plain Python, no numpy. Points and directions are world-space 3-lists.
"""
from __future__ import annotations

import math

from . import aim, shape_size

TARGET = 3.0                 # the spot's light from a new key: a pale surface reads light grey, not white (measured, brief 10)
SIZE_TIMES = 4.0             # a highlight light stands 4 × the item's size away
UPRIGHT = {"strip": 90.0}    # roll after aiming: a strip stands on end
PLACEABLE = ("rect", "disk", "strip", "sphere", "spot", "distant")


def _unit(v):
    n = math.hypot(*v)
    if n < 1e-12:
        raise ValueError("a direction of zero length")
    return [x / n for x in v]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def surface_normal(eye, hits) -> list[float]:
    """The surface's direction at the first pick, facing `eye`: the engine's own when its pick gives one, else from the
    two neighbour picks (an engine before pick answered `normal`)."""
    n = hits[0].get("normal")
    if n and math.hypot(*n) > 1e-9:
        n = _unit(n)
        return n if _dot(n, _sub(eye, hits[0]["point"])) > 0 else [-x for x in n]
    return normal_of(eye, *[h["point"] for h in hits])


def normal_of(eye, p0, p1, p2):
    """The surface's direction at p0 from two nearby points on it (picked a few pixels right and below), facing `eye`."""
    a, b = _sub(p1, p0), _sub(p2, p0)
    n = _unit([a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]])
    return n if _dot(n, _sub(eye, p0)) > 0 else [-x for x in n]


def area(kind: str, v: dict) -> float:
    """The glowing area that the brightness rule divides by (m²); a sun has none (its intensity is the light itself)."""
    if kind == "rect":
        return v.get("width", 1.0) * v.get("height", 1.0)
    if kind == "strip":
        return v.get("length", 1.2) * v.get("width", 1.0)
    if kind in ("disk", "sphere", "spot"):
        return math.pi * v.get("radius", 0.5) ** 2
    return 1.0


def start_intensity(kind: str, v: dict, distance: float) -> float:
    """The intensity that gives `TARGET` of light at `distance` metres, for this light's size and exposure."""
    if kind == "dome":
        return 1.0
    d2 = max(distance, 0.05) ** 2
    per = 1.0 if kind == "distant" else d2 if v.get("normalize") else d2 / max(area(kind, v), 1e-6)
    return round(TARGET * per / 2.0 ** v.get("exposure", 0.0), 3)


def place(kind: str, eye, point, normal, distance: float) -> dict:
    """World position, aim and roll for a light of `kind` so its highlight (a sun: its lit side) lands on `point`."""
    if kind not in PLACEABLE:
        raise ValueError(f"a {kind} light is around everything; place a panel, bulb, spot or sun by its highlight")
    n, look = _unit(normal), _unit(_sub(point, eye))
    if _dot(look, n) > 0:
        raise ValueError("that side of the surface faces away from the camera")
    way = n if kind == "distant" else _sub(look, [2 * _dot(look, n) * c for c in n])       # the view ray, bounced
    if point[1] + distance * way[1] < 0 <= point[1]:      # its mirror spot is under the floor: the same angle from above
        way = [way[0], -way[1], way[2]]
    pos = [p + distance * w for p, w in zip(point, way)]
    return {"x": pos[0], "y": pos[1], "z": pos[2], "aim": "point", "aimX": point[0], "aimY": point[1], "aimZ": point[2],
            "roll": UPRIGHT.get(kind, 0.0)}


def item_size(world, v: dict) -> float | None:
    """A mesh's largest extent in metres (its shape's size times its world scale); None when the shape has no size."""
    size = shape_size.extent(v)
    if not size:
        return None
    scale = max(math.hypot(*(world[0][r][c] for r in range(3))) for c in range(3))
    return size * scale


def distance_for(size: float | None, eye, point) -> float:
    """4 × the item's size; without a size, a third of the way from the spot back to the camera."""
    return SIZE_TIMES * size if size else max(0.3, math.dist(eye, point) / 3)


def to_parent(parent_world, values: dict) -> dict:
    """World x y z of `values` turned into the parent's space (the aim target stays in the world)."""
    lin, t = parent_world
    inv = aim._inverse(lin)
    local = aim._apply(inv, _sub([values["x"], values["y"], values["z"]], t))
    return {**values, "x": local[0], "y": local[1], "z": local[2]}


def start_values(params, given: dict) -> dict:
    """`light.add`'s fields with the starting brightness worked out (when no intensity is given) and a strip on end."""
    v = {p.name: p.default for p in params} | given
    out = dict(given)
    if v["kind"] == "strip" and v["aim"] == "none" and "rz" not in given:
        out["rz"] = 90.0
    if "intensity" not in given:
        here = [v["x"], v["y"], v["z"]]
        there = [v["aimX"], v["aimY"], v["aimZ"]] if v["aim"] == "point" else [0.0, 0.0, 0.0]
        out["intensity"] = start_intensity(v["kind"], v, math.dist(here, there))
    return out
