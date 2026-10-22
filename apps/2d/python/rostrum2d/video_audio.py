"""A video file's own sound, as 2D reads it: whether there is one (ffprobe, once per file) and a small mono WAV of it
for the timeline's Video sound row to draw (ffmpeg, once per file, in a capped cache). 2D never plays or mixes it:
RostrumSound does, from the video file itself (sync_sound.py). No Qt.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from . import settings

CACHE_DIR = settings.cache_dir("2d-video-sound")
KEEP = 24                    # WAVs kept (a few hundred KB each: 8 kHz mono)
RATE = 8000
_AUDIO: dict = {}            # (path, size, mtime) -> has a sound stream


def _key(path: Path) -> tuple:
    st = path.stat()
    return str(path), st.st_size, st.st_mtime_ns


def has_audio(path: Path) -> bool:
    key = _key(path)
    if key not in _AUDIO:
        r = subprocess.run([settings.ffmpeg("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries",
                            "stream=codec_name", "-of", "csv=p=0", str(path)], capture_output=True, text=True,
                           timeout=60, creationflags=settings.NO_WINDOW)
        if r.returncode != 0:
            raise RuntimeError(f"ffprobe could not read {path}: {r.stderr.strip()[-300:]}")
        _AUDIO[key] = bool(r.stdout.strip())
    return _AUDIO[key]


def wav(path: Path) -> Path:
    """The video's sound as an 8 kHz mono WAV (made once; the name is the file's path, size and time)."""
    path = Path(path)
    out = CACHE_DIR / (hashlib.sha256(repr(_key(path)).encode()).hexdigest()[:24] + ".wav")
    if out.is_file():
        out.touch()
        return out
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".partial.wav")
    r = subprocess.run([settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-vn", "-ac", "1",
                        "-ar", str(RATE), str(tmp)], capture_output=True, text=True, timeout=300,
                       creationflags=settings.NO_WINDOW)
    if r.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg could not read the sound of {path} (exit {r.returncode}): {r.stderr.strip()[-300:]}")
    tmp.replace(out)
    for old in sorted(CACHE_DIR.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)[KEEP:]:
        old.unlink(missing_ok=True)
    return out
