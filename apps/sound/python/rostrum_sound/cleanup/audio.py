"""Reading and writing the audio a cleanup step works on: any file the engine reads, as float32 [channels, n]."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from rostrum_core import RostrumError, codes

from ..listen.dsp import resample


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
        x = resample(x, sr, rate, axis=1).astype(np.float32)
    return x, sr


def write(path, x: np.ndarray, rate: int):
    """Write float32 [channels, n] as a 32-bit float WAV (what the engine writes); a non-finite sample fails loudly."""
    if not np.isfinite(x).all():
        raise RostrumError(codes.JOB_FAILED, "cleanup", Path(path).name, "came out with non-finite samples")
    sf.write(str(path), x.T, rate, subtype="FLOAT")


MONO_SIDE_DB = -40.0     # side (L-R) this far under the middle (L+R) is not heard as stereo


def is_mono(x: np.ndarray, side_db: float = MONO_SIDE_DB) -> bool:
    """One channel, or two so alike (a separated voice stem, a mono take panned) that their difference is under
    `side_db`: a model is then run once on the middle instead of twice on nearly the same signal."""
    if x.shape[0] == 1:
        return True
    mid, side = float(np.sum((x[0] + x[1]) ** 2)), float(np.sum((x[0] - x[1]) ** 2))
    return side <= mid * 10 ** (side_db / 10)


def middle(x: np.ndarray) -> np.ndarray:
    return x[0] if x.shape[0] == 1 else 0.5 * (x[0] + x[1])
