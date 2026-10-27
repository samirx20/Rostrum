"""Imports: bring in a 3D file (USD, glTF / GLB, OBJ, FBX or Alembic) by reference; the file is never rewritten. The
core turns the other formats into USD (core/src/convert.h), so everything after that is the same USD import.

With an engine (the app and the MCP server hand theirs over through ops_mesh.use_engine) `import.add` reads the file
first (the engine's inspect_usd) and then: scales the import to metres when the file says it is in another unit
(`fileUnit` keeps what the file was in; `unit_note` is the sentence the screen shows once), stands a Z-up file
upright, lands the import's base (the bottom middle of its bounds) on x y z, and lists the file's meshes as parts,
each of which can then get its own material or be hidden. `import.keep_size` goes back to the file's own numbers.
Without an engine (a plain script) x y z is where the import's origin goes and nothing is read or rescaled.
"""
from __future__ import annotations

import itertools
import math
from pathlib import Path

from rostrum_core import Param
from rostrum_core.errors import codes

from . import build, fields as F
from .kind import REGISTRY as R
from .ops_items import PLACE, _holder, new_item

# What an import reads, in the order the Import menu offers them (the core's convert.cpp has the same extensions).
FORMATS = [
    {"name": "glTF", "label": "glTF / GLB", "extensions": [".gltf", ".glb"]},
    {"name": "OBJ", "label": "OBJ", "extensions": [".obj"]},
    {"name": "FBX", "label": "FBX", "extensions": [".fbx"]},
    {"name": "Alembic", "label": "Alembic", "extensions": [".abc"]},
    {"name": "USD", "label": "USD", "extensions": [".usd", ".usda", ".usdc", ".usdz"]},
]
EXTENSIONS = tuple(e for f in FORMATS for e in f["extensions"])
UNIT_NAMES = {0.001: "millimetres", 0.01: "centimetres", 0.1: "decimetres", 0.0254: "inches", 0.3048: "feet",
              0.9144: "yards", 1000.0: "kilometres"}
SHAPES = {"Mesh", "Cube", "Sphere", "Cylinder", "Cone", "Capsule", "Plane", "BasisCurves", "NurbsPatch", "Points"}   # USD's drawn prims
MAX_PARTS = 64                  # more meshes than this: the file's top-level pieces are listed instead

_INSPECT = None                 # file path -> the engine's inspect_usd answer (ENGINE_CONTRACT.md)


def use_engine(engine):
    """Let import.add read a file through this engine (None: no reading, no rescale)."""
    global _INSPECT
    _INSPECT = engine.inspect_usd if engine is not None else None


def use_inspect(fn):
    """Tests: any file -> inspect answer function."""
    global _INSPECT
    _INSPECT = fn


def unit_name(meters: float) -> str:
    for m, name in UNIT_NAMES.items():
        if math.isclose(meters, m, rel_tol=1e-6):
            return name
    return f"units of {meters:g} m"


def unit_note(item: dict) -> str:
    """The sentence the screen says once after an import was rescaled ("" when it wasn't)."""
    unit = item.get("fileUnit", 1.0)
    if math.isclose(unit, 1.0):
        return ""
    inverse = 1 / unit
    at = f"1/{inverse:.4g}" if inverse > 1 else f"{unit:g}×"         # 1/100, 1/39.37; 1000× from kilometres
    return f"Imported at {at}: it was in {unit_name(unit)}"


def _parts(info: dict) -> list[str]:
    """The file's meshes as part paths relative to its default prim (or its top pieces when there are too many)."""
    root = info.get("defaultPrim") or ""
    if not root:
        return []
    below = [p for p in info.get("prims", []) if p["path"].startswith(root + "/")]
    meshes = [p for p in below if p["type"] in SHAPES]
    if len(meshes) > MAX_PARTS:
        meshes = [p for p in below if p["path"].count("/") == root.count("/") + 1][:MAX_PARTS]
    return [p["path"][len(root) + 1:] for p in meshes if "/Materials" not in p["path"][len(root):]]


def _bounds(info: dict):
    root = info.get("defaultPrim") or ""
    for p in info.get("prims", []):
        if p["path"] == root and p.get("bounds"):
            return p["bounds"]
    return None


def _turn_x(v, degrees):
    a = math.radians(degrees)
    x, y, z = v
    return x, y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)


def base_offset(bounds, scale: float, rx: float) -> tuple[float, float, float]:
    """Where the bottom middle of `bounds` (file space) lands after the import's scale and X turn, from its origin."""
    corners = [_turn_x([c * scale for c in corner], rx) for corner in itertools.product(*zip(*bounds))]
    xs, ys, zs = zip(*corners)
    return (min(xs) + max(xs)) / 2, min(ys), (min(zs) + max(zs)) / 2


def read_file(values: dict, keep_size: bool = False) -> tuple[dict, list[str]]:
    """An import's fields (`values`: file, x y z where its base lands, …) after reading its file through the engine:
    scaled to metres, stood upright, its base on x y z; and the file's mesh paths to list as parts. Unchanged (and no
    parts) without an engine. import.add and the script's import_usd both come here, so both land the same."""
    if _INSPECT is None:
        return dict(values), []
    info, out = _INSPECT(values["file"]), dict(values)
    unit = info.get("metersPerUnit") or 1.0
    scale = 1.0 if keep_size or not info.get("unitsKnown", True) else unit
    rx = -90.0 if info.get("upAxis") == "Z" and "rx" not in values else values.get("rx", 0.0)
    out.update(sx=scale, sy=scale, sz=scale, rx=rx, fileUnit=scale)
    if (bounds := _bounds(info)) is not None:
        off = base_offset(bounds, scale, rx)
        out.update({k: values.get(k, 0.0) - o for k, o in zip("xyz", off)})
    return out, _parts(info)


@R.operation("import.add", "Bring in a 3D file by reference: USD (.usd .usda .usdc .usdz), glTF (.gltf .glb), OBJ, FBX "
             "or Alembic (.abc, animation plays with the shot); the file is never rewritten. In the app and through "
             "MCP the file is read first: x y z is where its base (bottom middle) lands, a file in another unit is "
             "scaled to metres (fileUnit keeps what it was in; import.keep_size undoes it; keepSize skips it), a Z-up "
             "file is stood upright, and its meshes are listed as parts (each can get its own material or be hidden). "
             "`parts`: extra prim paths (from inspect_model_file) to list.", label="Import",
             params=[*PLACE, Param.toggle("keepSize", label="Keep the file's size", importance="deep",
                                          help="Don't scale a file in centimetres (or any other unit) to metres"),
                     Param.list("parts", "text", label="Parts", importance="deep",
                                help="Prim paths relative to the import's prim, e.g. Body/Screen"),
                     *F.unconditional("import")])
def import_add(ctx, targets, args):
    file = args.get("file") or ""
    if not file:
        ctx.fail(codes.BAD_ARGUMENT, '"file"', "is required", hint="The absolute path of a " + " ".join(EXTENSIONS) + " file.")
    if Path(file).suffix.lower() not in EXTENSIONS:
        ctx.fail(codes.BAD_ARGUMENT, f'file "{file}"', "is not a file an import reads", EXTENSIONS)
    fields = [p.name for p in F.FIELDS["import"]]
    try:
        values, paths = read_file({k: v for k, v in args.items() if k in fields}, args.get("keepSize", False))
    except Exception as e:  # noqa: BLE001  the engine's reason, named
        ctx.fail(codes.BAD_ARGUMENT, f'file "{file}"', f"could not be read: {e}")
    paths += [p for p in args.get("parts", []) if p not in paths]
    item = new_item(ctx, "import", args, values)
    for path in paths:
        item["parts"].append(build.make("part", build.part_id(item["id"], path),
                                        {"name": path.rsplit("/", 1)[-1], "path": path}, ctx.where))
    parent, key = _holder(ctx, args.get("into"))
    ctx.insert(parent, key, item, args.get("index"))
    return item


@R.operation("import.keep_size", "Undo an import's unit rescale: back to the file's own numbers (an import of a file in "
             "centimetres becomes 100 times bigger). Its other scaling stays.", target="import",
             label="Keep original size", importance="deep")
def import_keep_size(ctx, targets, args):
    for t in targets:
        item = ctx.item(t)
        unit = item.get("fileUnit", 1.0)
        if math.isclose(unit, 1.0):
            continue
        scales = {k: item.get(k, 1.0) for k in ("sx", "sy", "sz")}
        for k, v in scales.items():
            ctx.set(t, k, v / unit)
        ctx.set(t, "fileUnit", 1.0)
        bounds = _bounds(_INSPECT(item["file"])) if _INSPECT is not None else None
        if bounds is not None:          # grow around the base: it stays where it stood
            now, then = (base_offset(bounds, scales["sy"] * f, item.get("rx", 0.0)) for f in (1.0, 1 / unit))
            for k, a, b in zip("xyz", now, then):
                ctx.set(t, k, item.get(k, 0.0) + a - b)
