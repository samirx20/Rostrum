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
import tempfile
import uuid
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


def import_dir(folder, stem: str) -> Path:
    """Where the pictures an import makes (a PSD's layers, a Figma frame's images) are written: the project's
    imports/<stem>/. A scene not saved in a project yet has no folder: they go to a scratch folder of the computer, named
    by absolute path (so `outside` says they won't travel with the project) until the person has a project."""
    if folder:
        return Path(folder) / "imports" / stem
    return Path(tempfile.gettempdir()) / "rostrum2d-unsaved-imports" / uuid.uuid4().hex[:8] / stem


def outside(folder, item: dict) -> bool:
    """True for a file the project does not hold (an absolute path outside its folder)."""
    return P.media_outside(folder, item.get("src", ""))


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
        rel = P.media_place(folder, layer["src"])
        if rel:
            layer["src"], n = rel, n + 1
    return (new, f"{n} picture or video file{'s' if n != 1 else ''} made relative to the project") if n else None
