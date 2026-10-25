"""Where a picture's or video's file is: the ONE place an image / video layer's `src` becomes a file on disk.

A file kept in the project (import copies it to `media/image/` or `media/video/`, rostrum_core.project.add_file) is
stored RELATIVE to the project folder, so copying or moving the folder keeps every layer working. A file the person
points at outside the project stays the absolute path they gave (diagnose says so: it won't travel with the project).

`file(folder, item)` is the path to open; a file that is not there is loud, naming the layer and the file.
`upgrade` (DocKind.upgrade, on open) makes an older project's absolute paths relative when the file lies inside the
project folder, or in the folder this project was copied FROM (same place under media/ here).
A scene with no project yet keeps its imported files in the app's temporary store (`import_dir`); `keep_calls` is the ONE
rule that moves those into a project (called when the scene is first saved into a folder, files2d.save_into, and again on
open, `upgrade`, for any project that still names the store), so "File outside the project" never shows for them.
"""
from __future__ import annotations

import copy
import tempfile
import uuid
from pathlib import Path

from rostrum_core import RostrumError, codes, filestamps
from rostrum_core import project as P

TYPES = ("image", "video")


def file(folder, item: dict) -> Path:
    """The file an image / video layer shows; loud (layer and file named) when it isn't there."""
    path = P.media_file(folder, item["src"])
    if not filestamps.is_file(path):
        raise RostrumError(codes.NOT_FOUND, "render", f'{item.get("name") or item["id"]} ({item["id"]})', f"its file is missing: {path}",
                           hint="Point the layer at the file again (File field), or put the file back in the project folder.")
    return path


STORE = Path(tempfile.gettempdir()) / "rostrum2d-unsaved-imports"


def in_store(value) -> bool:
    """True for a file path inside the app's temporary store of an unsaved scene's imports."""
    try:
        return bool(value) and Path(value).is_absolute() and Path(value).resolve().is_relative_to(STORE.resolve())
    except OSError:
        return False


def keep_calls(layers, folder) -> list[dict]:
    """The `image.set` / `video.set` calls that move each layer's file out of the temporary store into the project (the
    file is copied to media/<type>/, the layer names it by its place there). A file already gone from the store is left
    alone (diagnose says "missing")."""
    calls = []
    for layer in layers:
        if in_store(layer["src"]) and Path(layer["src"]).is_file():
            row = P.add_file(folder, layer["type"], Path(layer["src"]).stem, layer["src"])
            calls.append({"op": f'{layer["type"]}.set', "target": [layer["id"]], "args": {"src": row["file"]}})
    return calls


def import_dir(folder, stem: str) -> Path:
    """Where the pictures an import makes (a PSD's layers, a Figma frame's images) are written: the project's
    imports/<stem>/. A scene not saved in a project yet has no folder: they go to a scratch folder of the computer, named
    by absolute path (so `outside` says they won't travel with the project) until the person has a project."""
    if folder:
        return Path(folder) / "imports" / stem
    return STORE / uuid.uuid4().hex[:8] / stem


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
    if folder is None or not any(True for _ in _layers(data)):     # no picture or video: no copy of a big document
        return None
    new, n = copy.deepcopy(data), 0
    for layer in _layers(new):
        if in_store(layer["src"]) and Path(layer["src"]).is_file():
            layer["src"], n = P.add_file(folder, layer["type"], Path(layer["src"]).stem, layer["src"])["file"], n + 1
            continue
        rel = P.media_place(folder, layer["src"])
        if rel:
            layer["src"], n = rel, n + 1
    return (new, f"{n} picture or video file{'s' if n != 1 else ''} made relative to the project") if n else None
