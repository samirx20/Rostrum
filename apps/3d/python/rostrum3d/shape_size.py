"""How big a mesh's own shape is (before its scale), from its fields: one place for the screen's placing on a surface
(app/screen3d/placing.py) and the script's `place_on`. Shapes are centred on their origin, up is +Y."""
from __future__ import annotations


def extent(v: dict) -> float:
    """The biggest size of the shape, metres; 0 for a flat floor (plane, disc) or a shape with no simple size."""
    s = v.get("shape")
    if s == "box":
        return max(v["width"], v["height"], v["depth"])
    if s == "sphere":
        return 2 * v["radius"]
    if s in ("cylinder", "cone", "capsule"):
        return max(2 * v["radius"], v["height"])
    if s == "torus":
        return 2 * (v["radius"] + v["tube"])
    return 0.0


def half_height(v: dict) -> float:
    """How far the shape's middle sits above its base along its own up (Y); 0 for flat or outline shapes."""
    s = v.get("shape")
    if s in ("box", "cylinder", "cone", "capsule"):
        return v["height"] / 2
    if s == "sphere":
        return v["radius"]
    if s == "torus":
        return v["tube"]
    return 0.0
