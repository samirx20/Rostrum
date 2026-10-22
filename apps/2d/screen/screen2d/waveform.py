"""The Sound row's waveform: peaks read once per rendered mix (the mix file is named by its content, so its path is
the key) and kept, never worked out while painting. No Qt.

    peaks(wav) -> {"seconds": 4.0, "rate": 100, "peaks": [0.0 … 1.0, …]}   # one peak per 1/rate s, both channels
"""
from __future__ import annotations

import numpy as np
import soundfile as sf

RATE = 100                  # peaks per second: a pixel column at any useful zoom
MOST = 40000                # a long song gets fewer per second, never more than this many

_DONE: dict[str, dict] = {}


def peaks(wav) -> dict:
    key = str(wav)
    if key not in _DONE:
        data, sr = sf.read(key, dtype="float32", always_2d=True)
        seconds = len(data) / sr
        rate = min(RATE, MOST / max(seconds, 1e-6))
        per = max(1, int(sr / rate))
        n = len(data) // per
        loud = np.abs(data[: n * per]).max(axis=1).reshape(n, per).max(axis=1) if n else np.zeros(0)
        _DONE.clear()                       # one mix plays at a time: keep only its peaks
        _DONE[key] = {"seconds": round(seconds, 4), "rate": sr / per,
                      "peaks": [round(float(v), 3) for v in np.minimum(loud, 1.0)],
                      "peak": round(float(np.abs(data).max()) if len(data) else 0.0, 4)}
    return _DONE[key]
