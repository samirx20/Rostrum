"""Copies (brief 24): one item holds a source (a mesh, an import, a group …) and the core draws it many times with
a UsdGeomPointInstancer, laid out in a line, a grid, a circle, over a surface or as a pour. An `effector` inside it changes the
copies near an item (bigger, turned, pushed, moved, hidden, tinted), within a field shape: a sphere round it, a wall (plane) through it,
or soft noise patches. A path layout runs the copies along the outlines of a text, SVG or drawing mesh (copies_path.py). The layout is computed in the core; this is the document's side:
the fields, the held copies (a copy someone put by hand: layout changes never move it) and the checks.
"""
from __future__ import annotations

from rostrum_core import Param

from .field_kit import CH, C, D, IS, N, NOT, P, S, T, TRANSFORM, X

LAYOUTS = ["line", "grid", "circle", "surface", "pour", "path"]
AMOUNT_BY = ["count", "density"]
KINDS = ["scale", "turn", "push", "move", "hide", "colour"]
FIELD_SHAPES = ["sphere", "plane", "noise"]          # an effector's `field`: where its change reaches
FALLOFFS = ["smooth", "linear"]
AXES = ["x", "y", "z"]
MAX_COUNT = 10000

LINE, GRID, CIRCLE, SURFACE, POUR, PATH = (IS("layout", v) for v in LAYOUTS)
CIRCLE_OR_POUR = {"any": [CIRCLE, POUR]}
POUR_KEYS = ("pourTime", "pourSpeed", "pourSpread")      # sent to the core only on a pour (compile.py)
PATH_KEYS = ("path", "alongPath", "pathShift")             # sent only on a path, with pathPoints / pathClosed (copies_path.py)
BY_DENSITY = {"all": [SURFACE, IS("amountBy", "density")]}
LINE_OR_GRID = {"any": [LINE, GRID]}
VARIED = {"any": [NOT("varyMove", 0.0), NOT("varyTurn", 0.0), NOT("varyScale", 0.0)]}
FALLING = IS("simulate", "falls")             # the copies item falls (sim/fields.py): only then can its copies start apart
HELD = "held"                                  # rows [copy, x, y, z, rx, ry, rz, s] in the copies item's own space
COPY_KEYS, COPY_KEYS_FROM = "copyKeys", "copyKeysFrom"   # keyed copies (copy_keys.py)

COPIES = [
    CH("layout", LAYOUTS, "Layout", "Copies", "line", P,
       help="Line: one after another. Grid: columns and rows. Circle: round a ring. Surface: scattered over another item. "
            "Pour: a stream from a mouth at the copies item's origin (falling: each appears when it leaves). "
            "Path: evenly along the outlines of a text, SVG or drawing"),
    N("count", "Count", "Copies", 1, MAX_COUNT, 1, "", P, {"not": BY_DENSITY}, integer=True, default=6,
      help="How many copies (a grid: the total, filled row by row)"),
    N("columns", "Columns", "Copies", 1, MAX_COUNT, 1, "", P, GRID, integer=True, default=4),
    N("spacingX", "Space X", "Copies", -1e4, 1e4, 0.001, "m", P, LINE_OR_GRID, default=0.2,
      help="A line: the step from one copy to the next. A grid: the step between columns"),
    N("spacingY", "Space Y", "Copies", -1e4, 1e4, 0.001, "m", S, LINE),
    N("spacingZ", "Space Z", "Copies", -1e4, 1e4, 0.001, "m", S, LINE_OR_GRID,
      help="A line: the step from one copy to the next. A grid: the step between rows"),
    N("radius", "Radius", "Copies", 0, 1e4, 0.001, "m", P, CIRCLE_OR_POUR, default=0.5,
      help="A circle: the ring's radius. A pour: the mouth's radius (each copy leaves from somewhere inside it)"),
    N("pourTime", "Pour for", "Copies", 0, 3600, 0.01, "s", P, POUR, default=2.0,
      help="The copies leave one after another, evenly over this long from Falls from (0: all at once)"),
    N("pourSpeed", "Speed", "Copies", 0, 100, 0.01, "m/s", P, POUR, default=0.0,
      help="How fast each leaves the mouth, along the copies item's own down (turn the copies item to aim it; 0: they drop)"),
    N("pourSpread", "Spread", "Copies", 0, 90, 0.1, "°", S, POUR, default=10.0,
      help="Each leaves up to this many degrees off the aim, so the stream fans out"),
    X("path", "Path", "Copies", "", P, PATH, refers="item",
      help="A text, SVG or drawing (path2d) mesh: the copies run along its outlines, each outline its share by length "
           "(a word: copies round every letter). Where it is at the shot's start counts; hide it if only the copies should show"),
    T("alongPath", "Face along it", "Copies", True, S, PATH,
      help="Each copy turns so its +X runs along the path and its up stands out of the path's flat side (off: as the source stands)"),
    N("pathShift", "Slide", "Copies", -1000, 1000, 0.01, "", S, PATH, default=0.0,
      help="Slides every copy along the path by this share of its length (1 = once round, 2 = twice); key it and the "
           "copies travel along the word over time"),
    T("faceOut", "Face outward", "Copies", True, S, CIRCLE, help="Each copy turns to face away from the middle"),
    X("surface", "Surface", "Copies", "", P, SURFACE, refers="item",
      help="The item the copies are scattered over (a plane, a mesh, a clay, an import)"),
    CH("amountBy", AMOUNT_BY, "Amount by", "Copies", "count", S, SURFACE,
       help="Count: this many in all. Density: this many for every square metre"),
    N("density", "Density", "Copies", 0, 1e5, 0.1, "per m²", P, BY_DENSITY, default=10.0),
    N("minSpacing", "Keep apart", "Copies", 0, 1e4, 0.001, "m", S, SURFACE,
      help="How far apart they stay; when the surface is full the rest come closer, so Count is met (0 = they may touch)"),
    T("alongSurface", "Stand on it", "Copies", True, S, SURFACE,
      help="Each copy stands along the surface's direction there (off: straight up)"),
    T("onTop", "Only on top", "Copies", True, S, SURFACE,
      help="Only the faces that look up, where things can rest (off: every side, the underside too)"),
    T("onlySeen", "Only what the camera sees", "Copies", True, S, SURFACE,
      help="Copies the shot camera never sees are not drawn or rendered (the report says how many were left out)"),
    N("seed", "Seed", "Vary", 0, 1e9, 1, "", S, integer=True, default=1,
      help="The same seed gives the same copies, whatever else changes"),
    N("varyMove", "Move", "Vary", 0, 1e4, 0.001, "m", P, help="Each copy shifts by up to this much, any way"),
    N("varyTurn", "Turn", "Vary", 0, 360, 0.1, "°", P, help="Each copy turns round up by up to this much"),
    N("varyScale", "Size", "Vary", 0, 1, 0.01, "", P, help="Each copy is up to this share smaller or bigger"),
    N("varyStart", "Start", "Vary", 0, 3600, 0.01, "s", P, FALLING,
      help="Each copy starts to fall up to this much later than Falls from, so they land one after another; each is "
           "hidden until it starts (no copies hanging in the air waiting)"),
    Param.points(HELD, label="Held copies", group="Copies data", importance=D, min=8, max=8, default=None, nullable=True, shown="script",
                 help="Rows [copy, x, y, z, rx, ry, rz, scale] in the copies item's own space: a copy put by hand. "
                      "A layout change never moves it; copies.release lets it go. Set by copies.hold"),
    Param.points(COPY_KEYS, label="Keyed copies", group="Copies data", importance=D, min=6, max=6, default=None, nullable=True,
                 shown="script", help="Rows [copy, prop 0-5 (x y z rx ry rz), t (s), v, ease (0 linear, 1 hold, 2 smooth), "
                                      "1 when Turn into keys wrote it]: copies that move by keys. Set by sim.to_keys and copies.key"),
    Param.text(COPY_KEYS_FROM, label="Keyed from", group="Copies data", importance=D, default="", shown="script",
               help="The simulation that wrote the keyed copies' keys (sim.to_keys)"),
] + TRANSFORM

# what the effector does, in the words the screen shows
EFFECTOR = [
    CH("kind", KINDS, "Changes", "Change near", "scale", P,
       help="Scale: bigger or smaller. Turn: tilts. Push: moves away from the centre. Move: moves one way (Axis). "
            "Hide: gone wherever the change is at least half. Colour: tints"),
    X("near", "Near", "Change near", "", P, refers="item",
      help="The item the change is centred on: it follows that item, so move it (or key it) and the change moves with it"),
    CH("field", FIELD_SHAPES, "Shape", "Change near", "sphere", P,
       help="Sphere: round the near item, fading out at Radius. Plane: a flat wall through the near item, facing its up: "
            "everything behind the wall is changed fully, in front it fades out over Radius (move or turn the near item to "
            "sweep it across). Noise: soft patches everywhere, about Radius big (move the near item and they drift)"),
    N("radius", "Radius", "Change near", 0, 1e4, 0.001, "m", P, default=0.5,
      help="Sphere: how far from the centre the change reaches. Plane: how wide the fade in front of the wall is. "
           "Noise: how big the patches are"),
    N("seed", "Seed", "Change near", 0, 1e9, 1, "", S, IS("field", "noise"), integer=True, default=1,
      help="Another seed, another pattern of patches"),
    CH("falloff", FALLOFFS, "Falloff", "Change near", "smooth", S, help="How the change fades out to its edge"),
    N("amount", "Amount", "Change near", -1e4, 1e4, 0.01, "", P, NOT("kind", "hide"), default=0.5,
      help="Scale: extra size at the centre (0.5 = half again bigger, −1 = gone). Turn: degrees. Push: metres away "
           "from the centre. Move: metres along Axis. Colour: 0–1 mix"),
    CH("axis", AXES, "Axis", "Change near", "y", S, {"any": [IS("kind", "turn"), IS("kind", "move")]},
       help="Turn: what each copy turns round (its own). Move: the way they move (the world's)"),
    C("colour", "Colour", "Change near", "#ff6a3d", P, IS("kind", "colour")),
]

KEYABLE = {"pathShift"}                       # copies numbers that may move over time (the core lays the path out per frame)
STILL = {"copies": {p.name for p in COPIES if p.type == "number" and p.name not in {q.name for q in TRANSFORM} | KEYABLE},
         "effector": {"kind", "near", "field", "seed", "falloff", "axis"}}
STARTING_AMOUNT = {"scale": 0.5, "turn": 30.0, "push": 0.2, "move": 0.2, "colour": 1.0}   # a new effector's amount when none is given (hide has none)


def held_map(item: dict) -> dict[int, dict]:
    """The copies item's held copies: {copy index: {x, y, z, rx, ry, rz, s}}."""
    return {int(r[0]): dict(zip(("x", "y", "z", "rx", "ry", "rz", "s"), r[1:])) for r in item.get(HELD) or []}


def held_rows(held: dict[int, dict]) -> list[list[float]] | None:
    """The rows to store (None when nothing is held: an empty list is not a valid set of points)."""
    if not held:
        return None
    return [[i, *(round(held[i][k], 6) for k in ("x", "y", "z", "rx", "ry", "rz", "s"))] for i in sorted(held)]


SOURCES = ("mesh", "combine", "import", "group", "clay")      # what a copies item can repeat (never a light, a camera, a rig or another copies)


def _inside(item: dict) -> set[str]:
    """Every id inside a copies item (its sources, what they hold, its effectors)."""
    out, stack = set(), list(item.get("children", []))
    while stack:
        c = stack.pop()
        out.add(c["id"])
        stack += c.get("children", [])
    return out


def path_problem(item: dict, by_id: dict) -> str | None:
    """Why a copies item's `path` can't be run along (none named, itself or inside it, not there, not an outline mesh),
    else None. `by_id`: every item of the document by id."""
    from .outline_fields import OUTLINE_SHAPES
    path = item.get("path") or ""
    if not path:
        return "its layout is path but path names no item (copies.set path=<id of a text, svg or path2d mesh>)"
    if path == item["id"] or path in _inside(item):
        return "can't run along itself or along what it copies"
    if path not in by_id:
        return f'path: no item "{path}" (there are: {", ".join(sorted(by_id)) or "none"})'
    p = by_id[path]
    if p.get("type") != "mesh" or p.get("shape") not in OUTLINE_SHAPES:
        what = f'a {p.get("shape")} mesh' if p.get("type") == "mesh" else f'a {p.get("type")}'
        return f'path "{path}" is {what}; a path is a text, svg or path2d mesh (its outlines are the path)'
    return None


def check(item: dict, problems: list, items: set, by_id: dict | None = None) -> None:
    """A copies item holds one or more sources and effectors, nothing else; its surface, path and held copies make
    sense. `by_id`: every item by id, for the path's kind (left out: the path is only checked to exist)."""
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
    if item.get("layout") == "path" and item.get("path"):       # none yet: allowed (the screen picks Layout, then Path); nothing is drawn
        why = path_problem(item, by_id if by_id is not None else {i: {"type": "mesh", "shape": "text"} for i in items})
        if why:
            problems.append(f"{where}: {why}")
    rows = item.get(HELD) or []
    seen = [int(r[0]) for r in rows]
    if len(set(seen)) != len(seen):
        problems.append(f"{where}: holds the same copy twice")
