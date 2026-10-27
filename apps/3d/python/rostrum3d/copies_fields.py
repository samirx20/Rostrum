"""Copies (brief 24): one item holds a source (a mesh, an import, a group …) and the core draws it many times with
a UsdGeomPointInstancer, laid out in a line, a grid, a circle or over a surface. An `effector` inside it changes the
copies near an item (bigger, turned, pushed away, tinted). The layout is computed in the core; this is the document's side:
the fields, the held copies (a copy someone put by hand: layout changes never move it) and the checks.
"""
from __future__ import annotations

from rostrum_core import Param

from .field_kit import CH, C, D, IS, N, NOT, P, S, T, TRANSFORM, X

LAYOUTS = ["line", "grid", "circle", "surface"]
AMOUNT_BY = ["count", "density"]
KINDS = ["scale", "turn", "push", "colour"]
FALLOFFS = ["smooth", "linear"]
AXES = ["x", "y", "z"]
MAX_COUNT = 10000

LINE, GRID, CIRCLE, SURFACE = (IS("layout", v) for v in LAYOUTS)
BY_DENSITY = {"all": [SURFACE, IS("amountBy", "density")]}
LINE_OR_GRID = {"any": [LINE, GRID]}
VARIED = {"any": [NOT("varyMove", 0.0), NOT("varyTurn", 0.0), NOT("varyScale", 0.0)]}
HELD = "held"                                  # rows [copy, x, y, z, rx, ry, rz, s] in the copies item's own space

COPIES = [
    CH("layout", LAYOUTS, "Layout", "Copies", "line", P,
       help="Line: one after another. Grid: columns and rows. Circle: round a ring. Surface: scattered over another item"),
    N("count", "Count", "Copies", 1, MAX_COUNT, 1, "", P, {"not": BY_DENSITY}, integer=True, default=6,
      help="How many copies (a grid: the total, filled row by row)"),
    N("columns", "Columns", "Copies", 1, MAX_COUNT, 1, "", P, GRID, integer=True, default=4),
    N("spacingX", "Space X", "Copies", -1e4, 1e4, 0.001, "m", P, LINE_OR_GRID, default=0.2,
      help="A line: the step from one copy to the next. A grid: the step between columns"),
    N("spacingY", "Space Y", "Copies", -1e4, 1e4, 0.001, "m", S, LINE),
    N("spacingZ", "Space Z", "Copies", -1e4, 1e4, 0.001, "m", S, LINE_OR_GRID,
      help="A line: the step from one copy to the next. A grid: the step between rows"),
    N("radius", "Radius", "Copies", 0, 1e4, 0.001, "m", P, CIRCLE, default=0.5),
    T("faceOut", "Face outward", "Copies", True, S, CIRCLE, help="Each copy turns to face away from the middle"),
    X("surface", "Surface", "Copies", "", P, SURFACE, refers="item",
      help="The item the copies are scattered over (a plane, a mesh, a clay, an import)"),
    CH("amountBy", AMOUNT_BY, "Amount by", "Copies", "count", S, SURFACE,
       help="Count: this many in all. Density: this many for every square metre"),
    N("density", "Density", "Copies", 0, 1e5, 0.1, "per m²", P, BY_DENSITY, default=10.0),
    N("minSpacing", "Keep apart", "Copies", 0, 1e4, 0.001, "m", S, SURFACE,
      help="No two copies closer than this (0 = they may touch)"),
    T("alongSurface", "Stand on it", "Copies", True, S, SURFACE,
      help="Each copy stands along the surface's direction there (off: straight up)"),
    T("onTop", "Only on top", "Copies", True, S, SURFACE,
      help="Only the faces that look up, where things can rest (off: every side, the underside too)"),
    T("onlySeen", "Only what the camera sees", "Copies", True, S, SURFACE,
      help="Copies the shot camera never sees are not drawn or rendered (the report says how many were left out)"),
    N("seed", "Seed", "Vary", 0, 1e9, 1, "", S, integer=True, default=1,
      help="The same seed gives the same copies, whatever else changes"),
    N("varyMove", "Move", "Vary", 0, 1e4, 0.001, "m", S, help="Each copy shifts by up to this much, any way"),
    N("varyTurn", "Turn", "Vary", 0, 360, 0.1, "°", S, help="Each copy turns round up by up to this much"),
    N("varyScale", "Size", "Vary", 0, 1, 0.01, "", S, help="Each copy is up to this share smaller or bigger"),
    Param.points(HELD, label="Held copies", group="Copies data", importance=D, min=8, max=8, default=None, nullable=True, shown="script",
                 help="Rows [copy, x, y, z, rx, ry, rz, scale] in the copies item's own space: a copy put by hand. "
                      "A layout change never moves it; copies.release lets it go. Set by copies.hold"),
] + TRANSFORM

# what the effector does, in the words the screen shows
EFFECTOR = [
    CH("kind", KINDS, "Changes", "Change near", "scale", P,
       help="Scale: bigger or smaller. Turn: tilts. Push: moves away from the centre. Colour: tints"),
    X("near", "Near", "Change near", "", P, refers="item",
      help="The item the change is centred on: it follows that item, so move it (or key it) and the change moves with it"),
    N("radius", "Radius", "Change near", 0, 1e4, 0.001, "m", P, default=0.5, help="How far from the centre the change reaches"),
    CH("falloff", FALLOFFS, "Falloff", "Change near", "smooth", S, help="How the change fades from the centre to the radius"),
    N("amount", "Amount", "Change near", -1e4, 1e4, 0.01, "", P, default=0.5,
      help="Scale: extra size at the centre (0.5 = half again bigger, −1 = gone). Turn: degrees. Push: metres away "
           "from the centre. Colour: 0–1 mix"),
    CH("axis", AXES, "Turn round", "Change near", "y", S, IS("kind", "turn")),
    C("colour", "Colour", "Change near", "#ff6a3d", P, IS("kind", "colour")),
]

STILL = {"copies": {p.name for p in COPIES if p.type == "number" and p.name not in {q.name for q in TRANSFORM}},
         "effector": {"kind", "near", "falloff", "axis"}}
STARTING_AMOUNT = {"scale": 0.5, "turn": 30.0, "push": 0.2, "colour": 1.0}      # a new effector's amount when none is given


def held_map(item: dict) -> dict[int, dict]:
    """The copies item's held copies: {copy index: {x, y, z, rx, ry, rz, s}}."""
    return {int(r[0]): dict(zip(("x", "y", "z", "rx", "ry", "rz", "s"), r[1:])) for r in item.get(HELD) or []}


def held_rows(held: dict[int, dict]) -> list[list[float]] | None:
    """The rows to store (None when nothing is held: an empty list is not a valid set of points)."""
    if not held:
        return None
    return [[i, *(round(held[i][k], 6) for k in ("x", "y", "z", "rx", "ry", "rz", "s"))] for i in sorted(held)]


SOURCES = ("mesh", "combine", "import", "group", "clay")      # what a copies item can repeat (never a light, a camera, a rig or another copies)


def check(item: dict, problems: list, items: set) -> None:
    """A copies item holds one or more sources and effectors, nothing else; its surface and held copies make sense."""
    kids = item.get("children", [])
    where = f'copies {item["id"]}'
    for c in kids:
        if c.get("type") not in (*SOURCES, "effector"):
            problems.append(f'{where}: {c["id"]} is a {c.get("type")}; copies repeat a mesh, combine, import, group or clay')
    if not any(c.get("type") in SOURCES for c in kids):
        problems.append(f"{where}: has nothing to copy (put a mesh, import or group inside it, or make it with copies.make)")
    if item.get("layout") == "surface":
        surface = item.get("surface") or ""
        if not surface:
            problems.append(f"{where}: its layout is surface but surface names no item (copies.set surface=<item id>)")
        elif surface == item["id"] or surface in {c["id"] for c in kids}:
            problems.append(f"{where}: can't be scattered over itself or over what it copies")
        elif surface not in items:
            problems.append(f'{where}.surface: no item "{surface}" (there are: {", ".join(sorted(items)) or "none"})')
    rows = item.get(HELD) or []
    seen = [int(r[0]) for r in rows]
    if len(set(seen)) != len(seen):
        problems.append(f"{where}: holds the same copy twice")
