"""Recorded audio as the engine reads it: raw little-endian f32, stereo interleaved, at the mix's rate.

Decoded once into a cache folder, keyed by the file's path, size, modified time and the target rate,
so a script that re-renders never decodes the same take twice.
"""
import hashlib
import os
from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


@dataclass(frozen=True)
class Pcm:
    file: str
    channels: int
    frames: int

    def to_json(self):
        return {"file": self.file, "channels": self.channels, "frames": self.frames}


def _key(path: Path, rate: int) -> str:
    st = path.stat()
    raw = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}|{rate}|v1"
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


def decode(src, rate: int, cache_dir, offset: float = 0.0, length: float | None = None) -> Pcm:
    """The file at `src` as stereo f32 PCM at `rate` Hz, in `cache_dir` (decoded on first use).
    `offset` / `length` (seconds) cut one take out of a longer recording."""
    if offset or length:
        whole = decode(src, rate, cache_dir)
        a = int(round(offset * rate))
        b = whole.frames if length is None else min(whole.frames, a + int(round(length * rate)))
        if not 0 <= a < b:
            raise ValueError(f"{src}: take {offset} s + {length} s is outside the file ({whole.frames / rate:.2f} s)")
        out = Path(whole.file).with_name(f"{Path(whole.file).stem}-{a}-{b}.f32")
        if not out.is_file():
            np.fromfile(whole.file, dtype="<f4").reshape(-1, 2)[a:b].tofile(out)
        return Pcm(str(out), 2, b - a)
    path = Path(src)
    if not path.is_file():
        raise FileNotFoundError(f"sample file not found: {path}")
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{path.stem[:40]}-{_key(path, rate)}.f32"
    meta = out.with_suffix(".frames")
    if out.is_file() and meta.is_file():
        return Pcm(str(out), 2, int(meta.read_text()))
    data, file_rate = sf.read(str(path), dtype="float32", always_2d=True)
    if data.shape[0] == 0:
        raise ValueError(f"sample file has no audio: {path}")
    data = data[:, :2] if data.shape[1] >= 2 else np.repeat(data, 2, axis=1)
    if file_rate != rate:
        g = gcd(int(file_rate), int(rate))
        data = resample_poly(data, rate // g, int(file_rate) // g, axis=0).astype(np.float32)
    tmp = out.with_suffix(f".tmp{os.getpid()}")
    np.ascontiguousarray(data, dtype="<f4").tofile(tmp)
    os.replace(tmp, out)
    meta.write_text(str(data.shape[0]))
    return Pcm(str(out), 2, int(data.shape[0]))
