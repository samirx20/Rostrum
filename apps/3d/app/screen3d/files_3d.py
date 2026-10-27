"""Rostrum3D's thin adapter to the kit's one file model (shared/gui-kit/FILES.md): a scene is one 3D document in a
project folder (`<folder>/docs/<item>.trd`); a new one is "Untitled scene" (then 2, 3 …) in the projects folder, built
from the start scene (rostrum3d/start_scene.py: a ground, the Studio sky, the shot camera "Shot 1"). Every window is live, so there is no Save: the kit's
ProjectFiles does New, Open, Open recent, Duplicate, Save a version, Show folder and the start screen. No Qt here.
"""
from __future__ import annotations

import os
from pathlib import Path

from rostrum_core import Document, RostrumError, codes, project
from rostrum_gui.docfiles import AppFiles
from rostrum3d import KIND
from rostrum3d.script import run_source
from rostrum3d.start_scene import SOURCE

ITEM = "scene"                     # a new scene's item id inside its project folder
GUIDES = Path(__file__).resolve().parents[2] / "python" / "rostrum3d" / "guides"


def projects_dir() -> Path:
    """Where New puts scenes: the person's own Documents folder (a scripted run: projects_root in docfiles uses scratch)."""
    return Path(os.environ["ROSTRUM_PROJECTS_DIR"]) if os.environ.get("ROSTRUM_PROJECTS_DIR") else Path.home() / "Documents" / "Rostrum3D"


def blank(folder: Path | None) -> Document:
    """A new scene (the start scene: a ground, the Studio sky, Shot 1's camera), saved in `folder` (None: in memory)."""
    doc = Document.new(KIND, folder=folder, item=ITEM if folder else None)
    doc.run_script("start.py", run_source(SOURCE, "start.py"))
    if folder:
        doc.save()
    return doc


def scene_item(folder) -> str:
    """The 3D document in a project folder: the only one, else the one changed most recently."""
    found = project.items(folder, "3d")
    if not found:
        raise RostrumError(codes.NOT_FOUND, "open", str(folder), "has no Rostrum3D scene in it",
                           hint=f"Pick a scene file ({KIND.ext}) or a project folder that has one in its docs folder. "
                                "Nothing was changed.")
    return max(found, key=lambda it: (Path(folder) / it["file"]).stat().st_mtime)["id"]


def resolve(path) -> tuple[Path, str]:
    """A scene file (`…/docs/<item>.trd`) or a project folder -> (project folder, item)."""
    p = Path(path)
    if p.is_file() and p.suffix == KIND.ext and p.parent.name == "docs":
        return p.parent.parent, p.stem
    if p.is_file():
        raise RostrumError(codes.BAD_ARGUMENT, "open", str(p), f"is not a Rostrum3D scene (a {KIND.ext} file in a "
                           "project's docs folder)", hint="Nothing was changed.")
    return p, scene_item(p)


def open_whole(folder, item) -> Document:
    return Document.open(folder, item, KIND)


FILES_3D = AppFiles(
    app="3d", title="Rostrum3D", noun="scene", ext=KIND.ext, untitled="Untitled scene", folder=projects_dir,
    blank=blank, open=open_whole, resolve=resolve,
    guides=[(GUIDES / "window.md", "The Rostrum3D window"), (GUIDES / "agents.md", "Working with an AI agent"),
            (GUIDES / "script.md", "Building a scene with a script")])
