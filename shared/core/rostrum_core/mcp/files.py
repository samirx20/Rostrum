"""Where look and render files go (one place for every app's look and render tools), and keeping the look folder small.

Look pictures belong to the project: with a project open they go to `<project>/looks/` (they travel with it and sit
beside its renders); with none, to the person's cache (a scripted run's scratch home). Replies give the absolute path."""
from __future__ import annotations

import time
from pathlib import Path

from .. import userhome

LOOK_DIR = Path.home() / ".rostrum" / "cache" / "look"
RENDER_DIR = Path.home() / ".rostrum" / "cache" / "render"
LOOK_KEEP = 200
PROJECT_LOOKS = "looks"         # the folder in a project that holds its look pictures


def _dir(kind: str, person: Path) -> Path:
    """The person's cache folder; a scripted run's goes to its scratch home (userhome.output_dir), never the person's."""
    return userhome.output_dir(f"cache-{kind}", person)


def look_folder(project=None, sub: str | None = None) -> Path:
    """The folder look pictures go to: `<project>/looks/[sub]` with a project (`doc.folder`), else the look cache.
    Made if missing; absolute."""
    folder = (Path(project) / PROJECT_LOOKS if project else _dir("look", LOOK_DIR)).resolve()
    folder = folder / sub if sub else folder
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def look_path(stem: str, ext: str = "png", project=None) -> Path:
    """A fresh file name in the look folder (`look_folder(project)`); the oldest files beyond LOOK_KEEP are deleted first."""
    folder = look_folder(project)
    old = sorted((p for p in folder.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)
    for p in old[:max(0, len(old) - LOOK_KEEP + 1)]:
        p.unlink(missing_ok=True)
    return folder / f"{stem}_{time.strftime('%H%M%S')}_{int(time.time() * 1000) % 1000:03d}.{ext}"


def render_path(stem: str, ext: str = "mp4") -> Path:
    folder = _dir("render", RENDER_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}.{ext}"


def render_cache_folder(stem: str) -> Path:
    """A new empty `<stem>_<time>.partial` folder for a render with no project folder (renamed when whole)."""
    root = _dir("render", RENDER_DIR)
    root.mkdir(parents=True, exist_ok=True)
    folder = root / f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}.partial"
    folder.mkdir()
    return folder
