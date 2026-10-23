"""Where a picture's or video's file is: the ONE place an image / video layer's `src` becomes a file on disk.

A file kept in the project (import copies it to `media/image/` or `media/video/`, rostrum_core.project.add_file) is
stored RELATIVE to the project folder, so copying or moving the folder keeps every layer working. A file the person
points at outside the project stays the absolute path they gave (diagnose says so: it won't travel with the project).

`file(folder, item)` is the path to open; a file that is not there is loud, naming the layer and the file.
`upgrade` (DocKind.upgrade, on open) makes an older project's absolute paths relative when the file lies inside the
project folder, or in the folder this project was copied FROM (same place under media/ here).
"""
from __future__ import annotations

import copy
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core import project as P

TYPES = ("image", "video")


def file(folder, item: dict) -> Path:
    """The file an image / video layer shows; loud (layer and file named) when it isn't there."""
    path = P.media_file(folder, item["src"])
    if not path.is_file():
        raise RostrumError(codes.NOT_FOUND, "render", f'{item.get("name") or item["id"]} ({item["id"]})', f"its file is missing: {path}",
                           hint="Point the layer at the file again (File field), or put the file back in the project folder.")
    return path


def outside(folder, item: dict) -> bool:
    """True for a file the project does not hold (an absolute path outside its folder)."""
    src = item.get("src", "")
    return bool(folder) and bool(src) and Path(src).is_absolute() and P.media_ref(folder, src) == src


def _layers(node):
    for key, value in node.items():
        for child in value if isinstance(value, list) else ():
            if isinstance(child, dict):
                if child.get("type") in TYPES and isinstance(child.get("src"), str) and child["src"]:
                    yield child
                yield from _layers(child)


def upgrade(data: dict, lists: dict, folder=None):
    """Older projects' absolute picture / video paths made relative: (new data, label) or None when nothing changes."""
    if folder is None:
        return None
    new, n = copy.deepcopy(data), 0
    for layer in _layers(new):
        rel = _inside(folder, layer["src"])
        if rel:
            layer["src"], n = rel, n + 1
    return (new, f"{n} picture or video file{'s' if n != 1 else ''} made relative to the project") if n else None


def _inside(folder, value: str) -> str | None:
    p = Path(value)
    if not p.is_absolute():
        return None
    rel = P.media_ref(folder, p)
    if rel != str(p):
        return rel
    parts = p.parts                                   # a copy's layers still name the original folder: same place under media/
    if "media" not in parts:
        return None
    tail = Path(*parts[len(parts) - 1 - parts[::-1].index("media"):])
    here = Path(folder) / tail
    if here.is_file() and (not p.is_file() or p.stat().st_size == here.stat().st_size):
        return tail.as_posix()
    return None
