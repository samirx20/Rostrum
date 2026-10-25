"""Shared helpers for the listening tools: read audio once, mono, dB, sections, JSON-safe numbers."""
import math
import os

import numpy as np
import soundfile as sf

BANDS = [("sub", 0, 60), ("low", 60, 250), ("low_mid", 250, 2000),
         ("high_mid", 2000, 6000), ("air", 6000, None)]
# The five bands of the render reply (`bands`, each track's `bands`): named and cut in the engine, analysis/balance.rs BANDS.
# Energy in each over where the sound is above -50 dBFS, in dB. Not the same cuts as BANDS above (the picture's).
RENDER_BANDS_HZ = {"sub": [20, 60], "bass": [60, 250], "lowMid": [250, 1000], "mid": [1000, 4000], "high": [4000, 16000]}
BAND_NAMES = [b[0] for b in BANDS]
LOW_END_HZ = 150.0
SPEECH_HZ = (1000.0, 4000.0)    # the region a voice is heard in (its consonants and presence)


def load(src):
    """-> (samples [n, channels] float32, sample rate). `src` is a path or an already
    loaded (samples, sr) pair (so a caller reads a file once and runs several tools)."""
    if isinstance(src, tuple):
        y, sr = src
        return (y[:, None] if y.ndim == 1 else y), sr
    path = os.fspath(src)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{path}: audio file not found")
    try:
        y, sr = sf.read(path, dtype="float32", always_2d=True)
    except Exception as e:
        from rostrum_core import RostrumError, codes
        raise RostrumError(codes.BAD_ARGUMENT, "listen", path, f"is not an audio file the ears read ({e})",
                           ["WAV", "FLAC", "OGG", "AIFF"],
                           "A video's sound: render_mix's WAV, or take the audio out of the video first.") from e
    if y.shape[0] == 0:
        raise ValueError(f"{path}: file has no audio")
    return y, sr


def is_float_file(src):
    """True when the file stores floating-point samples (they hold levels over 0 dBFS); False for fixed-point PCM
    (16/24/32-bit integer, which cannot) and for an already loaded (samples, sr) pair, which carries no format."""
    if isinstance(src, tuple):
        return False
    return sf.info(os.fspath(src)).subtype in ("FLOAT", "DOUBLE")


def name_of(src):
    return os.path.basename(os.fspath(src)) if not isinstance(src, tuple) else "audio"


def mono(y):
    return y.mean(axis=1)


def duration(y, sr):
    return y.shape[0] / sr


def db(power, floor=-120.0):
    """Linear power -> dB, clamped (silence reads as the floor, not -inf)."""
    return float(max(floor, 10 * math.log10(max(float(power), 1e-30))))


def peak_db(y):
    return db(float(np.max(np.abs(y))) ** 2)


def num(x, nd=2):
    """JSON-safe number: -inf / nan -> None."""
    x = float(x)
    return None if (math.isnan(x) or math.isinf(x)) else round(x, nd)


def sections(dur, length):
    """[(t0, t1)] covering the file in `length`-second pieces (the last may be short)."""
    if length <= 0:
        raise ValueError("section length must be > 0 seconds")
    n = max(1, math.ceil(dur / length - 1e-9))
    return [(i * length, min(dur, (i + 1) * length)) for i in range(n)]


def band_share(m, sr, bands=BANDS):
    """Share of a mono signal's energy per band, from one FFT -> {name: fraction}."""
    spec = np.abs(np.fft.rfft(m.astype(np.float64))) ** 2
    f = np.fft.rfftfreq(m.size, 1 / sr)
    total = max(spec.sum(), 1e-30)
    return {n: float(spec[(f >= lo) & ((f < hi) if hi else True)].sum() / total) for n, lo, hi in bands}


def band_power(m, sr, lo, hi):
    """Mean-square power of a mono signal between `lo` and `hi` Hz (from one FFT: the part of its mean square that lies
    there, so it adds up to the signal's own mean square across bands)."""
    spec = np.abs(np.fft.rfft(m.astype(np.float64))) ** 2
    f = np.fft.rfftfreq(m.size, 1 / sr)
    return 2 * float(spec[(f >= lo) & (f < hi)].sum()) / max(m.size, 1) ** 2
