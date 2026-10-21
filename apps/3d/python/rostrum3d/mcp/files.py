"""Where look and render files go, and keeping the look folder small (the same places as 2D's look tools)."""
from __future__ import annotations

import time
from pathlib import Path

LOOK_DIR = Path.home() / ".rostrum" / "cache" / "look"
RENDER_DIR = Path.home() / ".rostrum" / "cache" / "render"
LOOK_KEEP = 200


def look_path(stem: str, ext: str = "png") -> Path:
    """A fresh file name in the look folder; the oldest files beyond LOOK_KEEP are deleted first."""
    LOOK_DIR.mkdir(parents=True, exist_ok=True)
    old = sorted((p for p in LOOK_DIR.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)
    for p in old[:max(0, len(old) - LOOK_KEEP + 1)]:
        p.unlink(missing_ok=True)
    return LOOK_DIR / f"{stem}_{time.strftime('%H%M%S')}_{int(time.time() * 1000) % 1000:03d}.{ext}"


def render_cache_folder(stem: str) -> Path:
    """A new empty `<stem>_<time>.partial` folder for a render with no project folder (renamed when whole)."""
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    folder = RENDER_DIR / f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}.partial"
    folder.mkdir()
    return folder
