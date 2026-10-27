"""Placing on a surface (SPEC §4.1, §4.4): where a shape picked in the Shapes flyout lands when the person then clicks
in the viewport. The engine's pick gives the point and the surface's direction there (`normal`, facing the camera);
the shape stands along that direction with its base on the surface, sized to the spot: on a clay, a share of the
clay's width there (an eye on a face, surface_place.part_size); else to the scene's size class: a tenth of a metre in
an empty scene (product scale), else a fifth of the thing it was placed on (a 10 cm box on a 50 cm plinth).
Clicking empty space places it on the ground (y = 0) where the view's ray meets it. Standing on the point and the
mirrored copy on a mirrored clay are rostrum3d.surface_place's (shared with agents). Plain maths, no Qt.
"""
from __future__ import annotations

import math

from rostrum3d import aim
from rostrum3d.shape_size import extent
from rostrum3d.surface_place import clean, into_parent, mirrors, part_size, stand, up_turn  # noqa: F401  (one source)

PRODUCT = 0.1                        # the first shape in an empty scene, in metres (product scale)
FIFTH = 0.2                          # after that: this much of the thing it was placed on


def size_class(on_world, on_values: dict | None, clay: dict | None = None, point=None) -> float:
    """The new shape's size: on a clay (its document item) at `point`, sized for the spot (part_size); else a fifth
    of the item clicked on (its world size), else product scale."""
    if clay is not None and point is not None and (fit := part_size(clay, on_world, point)):
        return fit
    if not on_values:
        return PRODUCT
    scale = max(math.hypot(*(on_world[0][r][c] for r in range(3))) for c in range(3))
    size = extent(on_values) * scale * FIFTH
    return size if size > 0 else PRODUCT


def shape_fields(shape: str, size: float) -> dict:
    """The new shape's own fields for a shape `size` metres across, with the base on its local −Y side."""
    r = size / 2
    return {"box": {"width": size, "height": size, "depth": size, "bevel": round(size * 0.04, 5)},
            "sphere": {"radius": r},
            "cylinder": {"radius": r, "height": size, "bevel": round(size * 0.04, 5)},
            "cone": {"radius": r, "height": size},
            "capsule": {"radius": r / 2, "height": size},
            "torus": {"radius": r * 0.7, "tube": r * 0.3},
            "plane": {"width": size, "depth": size},
            "disc": {"radius": r}}.get(shape, {})


def ground_hit(view, x, y):
    """(point, normal) where the view's ray through picture px (x, y) meets the ground y = 0; None when it doesn't."""
    ray = view.ray(x, y)
    if ray[1] >= -1e-6:
        return None
    t = -view.eye[1] / ray[1]
    return [e + d * t for e, d in zip(view.eye, ray)], [0.0, 1.0, 0.0]


def placed(shape: str, point, normal, size: float) -> dict:
    """The mesh.add fields (top level, world space) for `shape` standing on the surface at `point` along `normal`."""
    f = shape_fields(shape, size)
    return {**f, **stand({"shape": shape, **f}, point, normal)}


# ---- text and logos (SPEC §4.4): an outline stands upright, never flat on the floor --------------------------------
UPRIGHT = 0.7                        # a surface whose normal is this much up (or more) is a top; less is a side


def outline_fields(shape: str, size: float) -> dict:
    """A new outline's size fields for the size class `size`: the em (text) or the drawing's width (a logo, twice
    that), a depth of a fifth of the em and a modest bevel."""
    big = {"size": size} if shape == "text" else {"svgWidth": round(2 * size, 5)}
    return {**big, "depth": round(size * 0.2, 5), "bevel": round(size * 0.01, 5)}


def facing(point, normal, eye) -> float:
    """The turn about Y (degrees) that points the outline's front (+Z) at the camera's `eye`; on a side, out of it."""
    nx, ny, nz = normal
    dx, dz = (nx, nz) if abs(ny) < UPRIGHT else (eye[0] - point[0], eye[2] - point[2])
    return math.degrees(math.atan2(dx, dz)) if math.hypot(dx, dz) > 1e-9 else 0.0


def outline_placed(point, normal, eye, below: float, depth: float) -> dict:
    """The mesh.add position and turn (world space) for an outline clicked at `point` on a surface along `normal`:
    upright, its front to the shot camera at `eye`. On a top (or the ground) its lowest point (`below` under its
    origin) sits on the surface; on a side it stands just in front of it (its back on the face)."""
    ry = facing(point, normal, eye)
    if abs(normal[1]) < UPRIGHT or normal[1] < 0:
        out = [p + n * depth / 2 for p, n in zip(point, normal)]
    else:
        out = [point[0], point[1] + below, point[2]]
    x, y, z = (round(v, 6) for v in out)
    return {"x": x, "y": y, "z": z, **({"ry": round(ry, 4)} if abs(ry) > 1e-4 else {})}
