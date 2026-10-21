"""Reading and writing the audio a cleanup step works on: any file the engine reads, as float32 [channels, n]."""
from __future__ import annotations

from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from rostrum_core import RostrumError, codes


def read(path, rate: int, channels: int = 2) -> tuple[np.ndarray, int]:
    """The file as float32 [channels, n] at `rate` (resampled if needed), and its own rate."""
    try:
        x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception as e:  # noqa: BLE001 - libsndfile's errors are plain RuntimeErrors
        raise RostrumError(codes.BAD_ARGUMENT, "cleanup", str(path), f"could not be read: {e}") from None
    if not len(x):
        raise RostrumError(codes.BAD_ARGUMENT, "cleanup", str(path), "has no audio")
    x = x.T
    if x.shape[0] == 1 and channels == 2:
        x = np.vstack([x, x])
    elif x.shape[0] > channels:
        x = x[:channels] if channels == 2 else x.mean(0, keepdims=True)
    if sr != rate:
        g = gcd(sr, rate)
        x = resample_poly(x, rate // g, sr // g, axis=1).astype(np.float32)
    return x, sr


def write(path, x: np.ndarray, rate: int):
    """Write float32 [channels, n] as a 32-bit float WAV (what the engine writes); a non-finite sample fails loudly."""
    if not np.isfinite(x).all():
        raise RostrumError(codes.JOB_FAILED, "cleanup", Path(path).name, "came out with non-finite samples")
    sf.write(str(path), x.T, rate, subtype="FLOAT")


def is_mono(x: np.ndarray) -> bool:
    return x.shape[0] == 1 or float(np.max(np.abs(x[0] - x[1]))) < 1e-6
