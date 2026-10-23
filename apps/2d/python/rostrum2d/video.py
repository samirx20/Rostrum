"""Video layers: the clip's frames decoded once, by the `ffmpeg` program (a separate process, as export), into a
content-keyed cache folder; the engine only picks a frame by the frame time (ENGINE_CONTRACT.md, video layer).

The cache key is the file's bytes + the size + the fit + the comp's fps + DECODER (bump it when the decode changes).
The video's own sound is not read here (RostrumSound owns sound).
"""
from __future__ import annotations

import hashlib
import math
import shutil
import subprocess
from pathlib import Path

from . import grain, looping, settings

CACHE_DIR = settings.cache_dir("2d-video")
CACHE_BYTES = 6 << 30            # size of CACHE_DIR before the oldest clips' folders go
DECODER = "1"

_FIT = {   # the decode's own size step, so the engine draws the pictures 1:1
    "stretch": "scale={w}:{h}",
    "cover": "scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
    "contain": "scale={w}:{h}:force_original_aspect_ratio=decrease",
}


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:24]


def source(item: dict, base: Path | None = None) -> Path:
    src = item.get("src", "")
    if not src:
        raise ValueError(f'{item["id"]}.src: a video layer needs a file')
    if grain.is_recipe(src):                     # film grain: made from its recipe (grain.py), never a stored path
        return grain.clip(src, f'{item["id"]}.src')
    p = Path(src)
    if not p.is_absolute() and base is not None:
        p = base / p
    if not p.is_file():
        raise FileNotFoundError(f'{item["id"]}.src: video file not found: {p}')
    return p


def pick(n: int, start: float, fps: float, speed: float, offset: float, count: int, loop: bool) -> int:
    """The clip's frame shown at comp frame `n` (the rule the engine uses, eval.rs `video_src`):
    floor((n − start·fps) · speed) + round(offset·fps), wrapped when looped, else held at the last frame."""
    i = math.floor((n - start * fps) * speed + 1e-6) + round(offset * fps)
    return looping.fold(i, count, looping.mode_of(loop))


def frames(item: dict, fps: float, base: Path | None = None) -> list[dict]:
    """`[{"at": i, "src": png}, …]` for every frame of the clip at `fps`, decoded now if the cache has none."""
    path, w, h = source(item, base), int(item["w"]), int(item["h"])
    if w < 2 or h < 2:
        raise ValueError(f'{item["id"]}: a video layer needs w and h of at least 2 px (it is {w}×{h})')
    fit = item.get("fit", "cover")
    key = hashlib.sha256(f"{_digest(path)}|{path.stat().st_size}|{w}x{h}|{fit}|{fps:g}|{DECODER}".encode()).hexdigest()[:32]
    folder = CACHE_DIR / key
    if not (folder / "done").is_file():
        _decode(item["id"], path, folder, w, h, fit, fps)
    shot = sorted(folder.glob("f*.png"))
    if not shot:
        raise RuntimeError(f'{item["id"]}: the cache holds no pictures of {path}: {folder}')
    folder.touch()
    return [{"at": i, "src": str(p)} for i, p in enumerate(shot)]


def _decode(id_: str, path: Path, folder: Path, w: int, h: int, fit: str, fps: float):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = folder.with_name(folder.name + ".partial")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    vf = f"fps={fps:g}," + _FIT[fit].format(w=w, h=h)
    cmd = [settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-an", "-vf", vf,
           "-start_number", "0", "-compression_level", "1", str(tmp / "f%06d.png")]
    run = subprocess.run(cmd, capture_output=True, text=True, creationflags=settings.NO_WINDOW)
    pictures = list(tmp.glob("f*.png"))
    if run.returncode != 0 or not pictures:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"{id_}: ffmpeg could not read {path} (exit {run.returncode}): {run.stderr.strip()[-400:]}")
    (tmp / "done").write_text(DECODER)
    shutil.rmtree(folder, ignore_errors=True)
    tmp.rename(folder)
    _trim()


def _trim():
    dirs = sorted((p for p in CACHE_DIR.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
    total = 0
    for d in dirs:                                   # newest kept first; past the cap the rest go
        total += sum(f.stat().st_size for f in d.iterdir())
        if total > CACHE_BYTES:
            shutil.rmtree(d, ignore_errors=True)
