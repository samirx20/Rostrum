"""UDIM tile sets (contract v1.34): one picture spread over several files, `name.1001.png`, `name.1002.png` …, named
together as `name.<UDIM>.png`. Tile 1001 covers u 0..1 v 0..1; tile = 1001 + u_tile + 10 * v_tile (u_tile 0..9).

The same rule as the core's udim.h (the engine checks a set and lists its tiles for Cycles): picking one tile of a set
picks the set (`as_set`), `tiles` lists the files there. material_scene sends every picture field through `as_set`.
"""
from __future__ import annotations

import re
from pathlib import Path

TOKEN = "<UDIM>"
FIRST, LAST = 1001, 1099
_TILE = re.compile(r"^(?P<stem>.*[._])(?P<tile>\d{4})$")       # "name.1001" or "name_1001" (the file's stem)

# The material fields that hold a picture (material_fields.MATERIAL); emissionTexture also takes one per frame.
PICTURES = ("baseColorTexture", "roughnessTexture", "metallicTexture", "bumpTexture", "emissionTexture")


def is_set(path: str) -> bool:
    return TOKEN in str(path)


def tile_path(path: str, tile: int) -> str:
    return str(path).replace(TOKEN, str(tile), 1)


def tile_numbers(path: str) -> list[int]:
    """The tile numbers of a set whose files exist, in order ([] for a path that is not a set)."""
    if not is_set(path):
        return []
    return [t for t in range(FIRST, LAST + 1) if Path(tile_path(path, t)).is_file()]


def tiles(path: str) -> list[str]:
    """The tile files of a set that exist, in tile order."""
    return [tile_path(path, t) for t in tile_numbers(path)]


def as_set(path: str) -> str:
    """One tile of a set, with at least one other tile of the same pattern beside it -> the set's `<UDIM>` path;
    anything else (a lone `x.1001.png` too, "" too) comes back unchanged."""
    if not path or is_set(path):
        return path
    p = Path(path)
    m = _TILE.match(p.stem)
    if not m or not FIRST <= int(m["tile"]) <= LAST:
        return path
    s = str(path)
    tail = 4 + len(p.suffix)                                    # the digits replaced in the text: separators kept
    candidate = s[:len(s) - tail] + TOKEN + p.suffix
    return candidate if any(t != int(m["tile"]) for t in tile_numbers(candidate)) else path


def describe(path: str) -> str:
    """How a look tool names a picture field's value: "UDIM set, N tiles (1001-1012)" or the file itself."""
    if not is_set(path):
        return path
    found = tile_numbers(path)
    if not found:
        return f"UDIM set with no tile found: {path}"
    return f"UDIM set, {len(found)} tile{'s' if len(found) != 1 else ''} ({found[0]}-{found[-1]}): {path}"
