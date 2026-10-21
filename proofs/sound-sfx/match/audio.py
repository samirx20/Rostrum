"""Reading a take and cutting it into model-sized windows.

A take is a file plus an optional in-point and length (the catalogue stores takes that way).
On the command line: `file.ogg`, or `file.ogg@0.29+1.39` (start 0.29 s, 1.39 s long).

Window choice (one place, so every caller embeds a take the same way):
- the model hears WINDOW seconds at a time (CLAP: 10 s at 48 kHz);
- a take up to one window long is used whole; shorter ones are padded by the model's feature
  extractor (silence by default, see `--pad`);
- a longer take is cut into windows with a half-window hop, and the LOUDEST `keep` windows
  (by RMS) are embedded and their embeddings averaged. Quiet tails and lead-ins then can't
  drown the event the agent is choosing the take for.
"""
import re
from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

_SPEC = re.compile(r"^(?P<path>.+?)@(?P<offset>[0-9.]+)(?:\+(?P<length>[0-9.]+))?$")


@dataclass
class Take:
    path: str
    offset: float = 0.0
    length: float | None = None

    @classmethod
    def parse(cls, spec: str) -> "Take":
        m = _SPEC.match(spec)
        if m and not Path(spec).is_file():
            ln = m.group("length")
            return cls(m.group("path"), float(m.group("offset")), float(ln) if ln else None)
        return cls(spec)

    @classmethod
    def from_dict(cls, d: dict) -> "Take":
        return cls(str(d["path"]), float(d.get("offset") or 0.0), d.get("length"))

    def label(self) -> str:
        if not self.offset and self.length is None:
            return self.path
        return f"{self.path}@{self.offset:g}" + (f"+{self.length:g}" if self.length is not None else "")


def load(take: Take, rate: int) -> np.ndarray:
    """Mono float32 at `rate`. Fails loudly on a missing file or an empty cut."""
    p = Path(take.path)
    if not p.is_file():
        raise FileNotFoundError(f"take not found: {p}")
    with sf.SoundFile(str(p)) as f:
        sr = f.samplerate
        f.seek(min(int(round(take.offset * sr)), f.frames))
        n = -1 if take.length is None else int(round(take.length * sr))
        x = f.read(frames=n, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if x.size == 0:
        raise ValueError(f"take is empty after cutting: {take.label()}")
    if sr != rate:
        g = gcd(sr, rate)
        x = resample_poly(x, rate // g, sr // g).astype(np.float32)
    return x


def windows(x: np.ndarray, rate: int, seconds: float, keep: int) -> list[np.ndarray]:
    """The loudest `keep` windows of `seconds` (half-window hop), in time order."""
    w = int(seconds * rate)
    if x.size <= w:
        return [x]
    hop = w // 2
    starts = list(range(0, x.size - w + 1, hop))
    if starts[-1] != x.size - w:
        starts.append(x.size - w)
    rms = [float(np.sqrt(np.mean(x[s:s + w] ** 2))) for s in starts]
    best = sorted(sorted(range(len(starts)), key=lambda i: -rms[i])[:keep])
    return [x[starts[i]:starts[i] + w] for i in best]
