"""Shot renders keep their finished frames: a stopped or failed sequence (mcp/sequence.py) or video (render_video) keeps its
`.partial` folder with `resume.json`, the hash of what was being rendered (the scene as drawn, the shot, its frames, the
renderer and its settings, size, file types, passes). Asking again for the very same render (same hash) continues in that
folder and draws only the frames still missing. A frame is reused only when every file it needs is there and whole (a PNG
ends with its IEND chunk; an EXR starts with its magic number); a stray half-written `<name>.partial` file is removed.
A stopped render that finished no frame leaves nothing. Any change to what is rendered gives another hash: a new folder.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
from pathlib import Path

from rostrum_core.errors import RostrumError
from rostrum_core.mcp.files import render_path

from . import draw

RESUME = "resume.json"
EXR_MAGIC = b"\x76\x2f\x31\x01"


def key_of(scene: dict, info: dict, f0: int, f1: int, renderer: str, size, settings: dict, formats, passes=None) -> str:
    """The hash a kept folder is matched by: everything that changes a frame's pixels or files."""
    what = {"scene": scene, "shot": info["id"], "camera": info["camera"], "fps": info.get("fps"), "frames": [f0, f1],
            "renderer": renderer, "size": list(size), "settings": settings, "formats": sorted(formats), "passes": sorted(passes or [])}
    return hashlib.sha256(json.dumps(what, sort_keys=True, default=str).encode()).hexdigest()


def kept_folders(folder, item_id: str | None, stem: str) -> list[Path]:
    """The `.partial` folders a render of this item could have left: the project's `renders/<item>/vNNN.partial`, else the render cache's."""
    if folder and item_id:
        base = Path(folder) / "renders" / item_id
        return sorted(base.glob("v*.partial")) if base.is_dir() else []
    return sorted(render_path(stem).parent.glob(f"{stem}_*.partial"))


def find(folder, item_id: str | None, stem: str, key: str) -> Path | None:
    """The newest kept folder whose resume.json has this hash, or None."""
    found = []
    for p in kept_folders(folder, item_id, stem):
        try:
            if json.loads((p / RESUME).read_text(encoding="utf-8")).get("key") == key:
                found.append(p)
        except (OSError, ValueError):
            continue
    return max(found, key=lambda p: p.stat().st_mtime, default=None)


def mark(partial: Path, key: str):
    (partial / RESUME).write_text(json.dumps({"key": key}), encoding="utf-8")


def whole(path: Path) -> bool:
    """A frame file that is complete: a PNG ending with IEND, an EXR starting with its magic number; never an empty one."""
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if path.suffix == ".png":
                f.seek(max(0, size - 12))
                return size > 20 and b"IEND" in f.read()
            if path.suffix == ".exr":
                return size > 64 and f.read(4) == EXR_MAGIC
        return size > 0
    except OSError:
        return False


def frame_file(folder: Path, name: str, frame: int, ext: str) -> Path:
    """The file the engine writes for a shot frame while rendering (`{frame}`: 4 digits at least)."""
    return folder / f"{name}.{frame:04d}.{ext}"


def finished(where: dict[str, Path], name: str, f0: int, f1: int, tidy: bool = False) -> list[int]:
    """The shot frames whose every file (`where`: type -> folder) is there and whole. `tidy` (only before drawing into the
    folder, never while a render writes there): half-written `.partial` files go."""
    for d in set(where.values()) if tidy else ():
        for stray in d.glob(f"{name}.*.partial"):
            stray.unlink(missing_ok=True)
    return [f for f in range(f0, f1 + 1) if all(whole(frame_file(d, name, f, ext)) for ext, d in where.items())]


def stretches(frames: list[int]) -> list[tuple[int, int]]:
    """[3, 4, 5, 9, 10] -> [(3, 5), (9, 10)]."""
    out: list[list[int]] = []
    for f in frames:
        if out and f == out[-1][1] + 1:
            out[-1][1] = f
        else:
            out.append([f, f])
    return [(a, b) for a, b in out]


def render_missing(where: str, what: str, engine, scene: dict, f0: int, f1: int, have: list[int], progress=None, **req) -> dict:
    """Draw only the frames of f0..f1 not in `have`, one engine call per stretch. `progress(done, total)` counts the kept
    frames as done. Returns the last engine reply ({} when nothing was missing)."""
    total, base, out = f1 - f0 + 1, len(have), {}
    missing = sorted(set(range(f0, f1 + 1)) - set(have))
    for a, b in stretches(missing):
        out = draw.render(where, what, engine, scene, frames=[a, b],
                          progress=(lambda i, n, _=None, b0=base: progress(b0 + i, total)) if progress else None, **req)
        base += b - a + 1
    return out


def continues_text(n: int) -> str:
    return f"Continues from {n} finished frame{'s' * (n != 1)}" if n else ""


@contextlib.contextmanager
def keeps_frames(partial: Path, count, stopped=None):
    """Around a shot render into `partial`: on a stop or failure the finished frames stay for a restart, and a RostrumError
    says so; a stop that finished no frame leaves nothing. `count()`: the frames finished so far."""
    try:
        yield
    except BaseException as e:
        n = count()
        if n == 0 and stopped is not None and stopped():
            shutil.rmtree(partial, ignore_errors=True)
        elif n and isinstance(e, RostrumError):
            e.hint = (e.hint + " " if e.hint else "") + (f"{n} finished frame{'s' * (n != 1)} are kept in {partial}; "
                                                          "rendering the same again continues from them.")
            e.args = (e.line(),)
        raise
