"""Run the built engine from a copy, never from the build folder itself.

Every agent session starts a 3D server, and each server's engine (rostrum3d-core.exe), the window's live-view module
(install/qml) and the stylized plug-in (hdRostrum.dll) stay open while it runs. Windows won't replace an open file, so
a rebuild failed at its install step ("file in use") whenever an agent was working. Now each user of a build runs a
copy of it: `%LOCALAPPDATA%\\Rostrum\\engine-cache\\<name>-<hash>`, the hash taken from the build's file names, sizes
and times, so a rebuild makes a new copy beside the old one and the running engines keep theirs. A copy nobody started
for a day is deleted, unless a running engine or window still holds a file in it (Windows then refuses to move it).

ROSTRUM3D_ENGINE_COPY=0 runs straight from the build folder (to debug a build in place).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path

KEEP_S = 24 * 3600                 # a copy not started for this long is deleted
USED = ".used"                     # touched each time a copy is handed out


def cache_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Rostrum" / "engine-cache"


def _files(folder: Path, only: tuple[str, ...] | None) -> list[Path]:
    tops = [folder / n for n in only] if only else sorted(folder.iterdir())
    out = []
    for t in tops:
        if t.is_dir():
            out += sorted(p for p in t.rglob("*") if p.is_file())
        elif t.is_file():
            out.append(t)
    return out


def _stamp(folder: Path, files: list[Path]) -> str:
    h = hashlib.sha1()
    for p in files:
        st = p.stat()
        h.update(f"{p.relative_to(folder).as_posix()}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:12]


def copy_of(folder: Path, name: str, only: tuple[str, ...] | None = None) -> Path:
    """The run copy of `folder` (just its entries `only`, when given), made when this build has none yet. Returns
    `folder` itself when it isn't built (the caller's own "not built" message then names the real place) or when
    ROSTRUM3D_ENGINE_COPY=0."""
    folder = Path(folder)
    if os.environ.get("ROSTRUM3D_ENGINE_COPY", "1") == "0" or not folder.is_dir():
        return folder
    files = _files(folder, only)
    if not files:
        return folder
    root = cache_root()
    dest = root / f"{name}-{_stamp(folder, files)}"
    if not dest.is_dir():
        part = root / f"{dest.name}.part-{os.getpid()}"
        shutil.rmtree(part, ignore_errors=True)
        for p in files:
            to = part / p.relative_to(folder)
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, to)
        try:
            part.rename(dest)                        # whole or not at all; another process may have won the race
        except OSError:
            shutil.rmtree(part, ignore_errors=True)
            if not dest.is_dir():
                raise
    (dest / USED).touch()
    _clean(root, name, dest)
    return dest


def _clean(root: Path, name: str, keep: Path):
    """Old copies of this name nobody started for KEEP_S, and parts a crashed copy left, are deleted (best effort)."""
    now = time.time()
    for d in root.glob(f"{name}-*"):
        if d == keep or not d.is_dir():
            continue
        used = d / USED
        when = used.stat().st_mtime if used.exists() else d.stat().st_mtime
        if now - when > KEEP_S:
            trash = root / f".trash-{d.name}-{os.getpid()}"
            try:
                d.rename(trash)                      # Windows refuses while a file in it is open: still running, kept
            except OSError:
                continue
            shutil.rmtree(trash, ignore_errors=True)
