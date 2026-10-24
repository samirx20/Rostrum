"""A voice clip as the phone model hears it: 16 kHz mono float32, cut to [start, end) seconds of the file."""
from __future__ import annotations

from math import gcd
from pathlib import Path

from rostrum_core import RostrumError, codes

RATE = 16000


def clip(wav, start: float = 0.0, end: float | None = None, where: str = "lipsync"):
    """(samples, seconds of the whole file). Any channel count and sample rate; a bad range is a loud error."""
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly

    path = Path(wav)
    if not path.is_file():
        raise RostrumError(codes.NOT_FOUND, where, f"audio {path}", "is not a file")
    try:
        data, rate = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception as e:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"audio {path}", f"could not be read: {e}") from e
    total = len(data) / rate
    stop = total if end is None else end
    if not 0 <= start < stop <= total + 1e-6:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"range {start}–{stop} s",
                           f"must lie inside the file (0–{total:.3f} s) with start before end")
    mono = data[int(round(start * rate)):int(round(stop * rate))].mean(axis=1)
    g = gcd(RATE, rate)
    out = mono if rate == RATE else resample_poly(mono, RATE // g, rate // g).astype(np.float32)
    return out, total
