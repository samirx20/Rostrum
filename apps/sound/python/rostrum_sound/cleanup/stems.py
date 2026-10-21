"""Stem separation: Open-Unmix UMX-HQ (MIT weights, MODELS.md) splits a mix into vocals, drums, bass and other.
The four stems are made together into one cache entry; a clip plays the one it names. The network runs as our ONNX
export (proofs/sound-cleanup/export_umxhq.py) on the CPU; the STFT and Wiener filtering are spectra.py."""
from __future__ import annotations

import numpy as np

from . import audio, models
from .spectra import istft, stft, wiener

STEP = "stems"
ENGINE = models.UMXHQ.engine
RATE, N, HOP = 44100, 4096, 1024
NAMES = ("vocals", "drums", "bass", "other")      # the graph's output order


def keyed(stem=None, **_):
    return {}                                      # one entry holds all four stems


def output(stem="vocals", **_):
    return f"{stem}.wav"


def separate(x: np.ndarray, progress=None) -> dict[str, np.ndarray]:
    """[2, n] at 44.1 kHz -> {stem: [2, n]}."""
    X = stft(x, N, HOP)
    s = models.session(models.UMXHQ)
    try:
        mags = s.run(None, {"mag": np.abs(X)[None].astype(np.float32)})[0][:, 0]   # [4, 2, bins, frames]
    finally:
        del s                                      # the model is released before the filtering
    Y = wiener(mags, X)
    return {name: istft(Y[i], N, HOP, x.shape[1]) for i, name in enumerate(NAMES)}


def run(src, folder, stem=None, **_):
    x, sr = audio.read(src, RATE)
    for name, y in separate(x).items():
        audio.write(folder / f"{name}.wav", y, RATE)
