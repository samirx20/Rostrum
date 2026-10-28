"""What a new clay step holds, worked out from what was given: the one rule for operations (ops_clay.py,
ops_clay_make.py) and scripts (script.py), so a person, an agent's call and a script make the same step.

- A piece: the blend at half its radius, the clay's own mirror when left out.
- A stroke: the clay's brush settings for what was left out.
- A drawn outline (clay_shapes.py): its plane and 2-D points, Puff 1, the blend at half how fat it is × Puff (capped
  5 cm): the same rule as a ball's half radius, so an arm's root swells into the body as one piece, no crease to open.
  A tiny one (fewer than 4 points, or thinner than 1.5 grains) is a lump at its middle, the brush's size.
- A spun profile: its plane (v = the axis) and [distance, height] points, the blend at half its widest.
- A new clay from a drawing stands where it was drawn (clay_shapes.standing) and its brush is a quarter of its size.
"""
from __future__ import annotations

from . import clay_shapes as G
from .clay_fields import CLAY

RADIUS = 0.15                  # a new clay's starting ball when nothing else is given
TINY = 1.5                     # thinner than this many grains: a lump
BLEND_SHARE, BLEND_CAP = 0.5, 0.05     # a drawn or spun piece's blend: × its half-thickness, as a ball's
DEFAULT = {p.name: p.default for p in CLAY}


def piece_values(clay: dict, args: dict, shape: str) -> dict:
    """A sphere or capsule's values: what was given, else the blend at half the radius and the clay's own mirror."""
    r = args.get("radius") or RADIUS
    values = {"step": "piece", "shape": shape, "at": args["at"], "radius": r, "mode": args.get("mode") or "add",
              "blend": args["blend"] if args.get("blend") is not None else round(r * 0.5, 6),
              "symmetry": args.get("symmetry") or clay["symmetry"], "name": args.get("name") or ""}
    if shape == "capsule":
        values["to"] = args["to"]
    return values


STROKE_FROM_CLAY = {"brush": "brush", "size": "brushSize", "strength": "brushStrength", "symmetry": "symmetry",
                    "accumulate": "accumulate", "falloff": "brushFalloff", "spacing": "brushSpacing",
                    "frontOnly": "frontOnly"}
PATHS = ("dabs", "dabList", "path")


def stroke_values(clay: dict, args: dict) -> dict:
    """A stroke step's values: the settings given, else the clay's brush settings (a CL1 clay without the CL2 ones:
    their defaults); `invert` only as given; its one path (dabs or path + dir)."""
    values = {k: args[k] if args.get(k) is not None else clay.get(own, DEFAULT[own])
              for k, own in STROKE_FROM_CLAY.items()}
    values["invert"] = bool(args.get("invert"))
    values.update({k: args[k] for k in (*PATHS, "dir") if args.get(k)})
    return {"step": "stroke", "name": args.get("name") or "", **values}


def _shared(clay: dict, args: dict, size: float) -> dict:
    blend = args["blend"] if args.get("blend") is not None else round(min(BLEND_SHARE * size, BLEND_CAP), 6)
    return {"mode": args.get("mode") or "add", "blend": blend, "symmetry": args.get("symmetry") or clay["symmetry"],
            "name": args.get("name") or ""}


def _lump(clay: dict, args: dict, points) -> dict:
    """A tiny drawing: a lump at its middle, the brush's size (`radius` when given)."""
    r = args.get("radius") or clay.get("brushSize") or DEFAULT["brushSize"]
    return piece_values(clay, {**args, "at": G.r6(G.mean(points)), "radius": r}, "sphere")


def draw_values(clay: dict, args: dict, points, grain: float) -> dict:
    """A drawn outline's step; `points` and `facing` in the clay's own space."""
    fit = G.fit_plane(points, args.get("facing")) if len(points) >= 3 else None
    if fit is None:
        return _lump(clay, args, points)
    outline = G.in_plane(points, *fit)
    fat = G.inner_radius(outline)
    if len(points) < 4 or fat < TINY * grain:
        return _lump(clay, args, points)
    return {"step": "piece", "shape": "outline", "plane": G.plane9(*fit), "outline": outline,
            "puff": float(args.get("puff") or 1.0), **_shared(clay, args, fat * float(args.get("puff") or 1.0))}


def spin_values(clay: dict, args: dict, points, grain: float) -> dict:
    """A spun profile's step; `points` and `axis` in the clay's own space."""
    frame = G.spin_frame(points, args.get("axis")) if len(points) >= 2 else None
    widest = max((r for r, _ in frame[3]), default=0.0) if frame else 0.0
    if frame is None or widest < TINY * grain:
        return _lump(clay, args, points)
    o, u, v, profile = frame
    return {"step": "piece", "shape": "spin", "plane": G.plane9(o, u, v), "profile": profile,
            **_shared(clay, args, widest)}


def size_of(values: dict) -> float:
    """About half a new step's largest measure (a ball: its radius): a new clay's brush is a quarter of it."""
    if values.get("shape") == "outline":
        pts = values["outline"]
        return max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in (0, 1)) / 2
    if values.get("shape") == "spin":
        hs = [h for _, h in values["profile"]]
        return max(max(r for r, _ in values["profile"]), (max(hs) - min(hs)) / 2)
    return float(values.get("radius", RADIUS))


def standing(args: dict) -> tuple[dict, dict]:
    """A new clay drawn (`draw`) or spun (`spin`) in the scene: (its x, y, z, ry, and the given arguments with the
    points, `facing` and `axis` moved into its own space as `points`)."""
    pts = args.get("draw") or args.get("spin")
    if args.get("draw"):
        fit = G.fit_plane(pts, args.get("facing")) if len(pts) >= 3 else None
        origin, turn = G.standing(pts, fit[1] if fit else G.X)
    else:
        frame = G.spin_frame(pts, args.get("axis"))
        origin, turn = G.standing(pts, frame[1] if frame else G.X, frame[0] if frame else None)
    local = {**args, "points": [G.r6(G.to_local(p, origin, turn)) for p in pts]}
    if args.get("facing"):
        local["facing"] = G.to_local(args["facing"], origin, turn, vector=True)
    if args.get("axis"):
        local["axis"] = [G.to_local(p, origin, turn) for p in args["axis"]]
    return {"x": origin[0], "y": origin[1], "z": origin[2], "ry": turn}, local
