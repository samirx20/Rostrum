"""Old documents' whole-picture grain layer (H32; today grain is a per-layer effect drawn by the engine: fields.py
`grain`, engine scene/grain.rs). Kept so those documents still open. Film grain as data: a grain layer's `src` is its recipe, `grain:<w>x<h>@<fps>#<seed>`, never a file path, so the
project opens on another computer and survives a cleaned cache. The noise clip (ffmpeg's `noise` filter, a fixed seed,
a different picture each frame) is made from the recipe when a video layer's source is resolved (video.source) and kept
in the cache, named by the recipe. Same recipe, same grain. No Qt.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from . import settings

CLIP_FRAMES = 12          # pictures in the loop: long enough not to be seen repeating at 24-30 fps
PREFIX = "grain:"
_RECIPE = re.compile(r"^grain:(\d+)x(\d+)@([0-9.]+)#(\d+)$")


def src_of(w: int, h: int, fps: float, seed: int) -> str:
    return f"{PREFIX}{w}x{h}@{fps:g}#{seed}"


def is_recipe(src: str) -> bool:
    return str(src).startswith(PREFIX)


def clip(src: str, where: str = "grain") -> Path:
    """The noise clip of a recipe: made once into the cache. A recipe that doesn't parse, or ffmpeg failing, is loud."""
    m = _RECIPE.match(src)
    if not m:
        raise ValueError(f'{where}: "{src}" is not a grain recipe (grain:<w>x<h>@<fps>#<seed>)')
    w, h, fps, seed = int(m[1]), int(m[2]), float(m[3]), int(m[4])
    name = "grain-" + hashlib.sha256(f"{w}x{h}|{fps:g}|{seed}|{CLIP_FRAMES}".encode()).hexdigest()[:12] + ".mkv"
    target = settings.cache_dir("2d-grain") / name
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".partial.mkv")
        vf = f"color=c=gray:s={w}x{h}:r={fps:g},noise=alls=100:allf=t:all_seed={seed}"
        run = subprocess.run([settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", vf,
                              "-frames:v", str(CLIP_FRAMES), "-c:v", "ffv1", str(tmp)], capture_output=True, text=True,
                             creationflags=settings.NO_WINDOW)
        if run.returncode != 0 or not tmp.is_file():
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"{where}: ffmpeg could not make the noise clip (exit {run.returncode}): "
                               f"{run.stderr.strip()[-400:]}")
        tmp.replace(target)
    return target
