"""Noise reduction: DeepFilterNet 3 (MIT OR Apache-2.0, MODELS.md) keeps speech and removes background noise.
The torchDF single-graph streaming export: 48 kHz, 480-sample hops, its whole state carried between hops, run on the
CPU (a hop is too small for the GPU to pay off). `strength` 1 removes all it can; lower keeps some room tone."""
from __future__ import annotations

import numpy as np

from . import audio, models

STEP = "denoise"
ENGINE = models.DFN3.engine
RATE, HOP, FFT = 48000, 480, 960
# The graph's output lags its input by the analysis window plus its two look-ahead hops: FFT - HOP + 2 * HOP = 1440
# samples (30 ms), measured by cross-correlation against the input (P9; the experiment removed only 480).
DELAY = FFT + HOP


def output(**_):
    return "denoised.wav"


def limit_db(strength: float) -> float:
    """The model's attenuation limit: 0 = no limit (strength 1), else at most this many dB taken off."""
    return 0.0 if strength >= 0.999 else max(3.0, -20 * np.log10(1 - strength))


def _channel(s, x: np.ndarray, limit: float) -> np.ndarray:
    padded = np.zeros(int(np.ceil((len(x) + DELAY) / HOP)) * HOP, np.float32)
    padded[:len(x)] = x
    out = np.empty_like(padded)
    states = np.zeros(s.get_inputs()[1].shape[0], np.float32)
    lim = np.array(limit, np.float32)
    for h in range(len(padded) // HOP):
        frame, states, _ = s.run(None, {"input_frame": padded[h * HOP:(h + 1) * HOP], "states": states,
                                        "atten_lim_db": lim})
        out[h * HOP:(h + 1) * HOP] = frame
    return out[DELAY:DELAY + len(x)]               # the model's delay removed: the take stays in time


def clean(x: np.ndarray, strength: float = 1.0, side_db: float = audio.MONO_SIDE_DB) -> np.ndarray:
    """[channels, n] at 48 kHz -> the same, denoised (a mono or near-mono take, such as a separated voice, is run once)."""
    s = models.session(models.DFN3)
    try:
        lim = limit_db(strength)
        if audio.is_mono(x, side_db):
            y = _channel(s, audio.middle(x), lim)
            return np.vstack([y] * x.shape[0])
        return np.vstack([_channel(s, c, lim) for c in x])
    finally:
        del s


def run(src, folder, strength=1.0, **_):
    x, _ = audio.read(src, RATE)
    audio.write(folder / output(), clean(x, float(strength)), RATE)
