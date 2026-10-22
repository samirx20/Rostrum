"""A cleaned take stays in time with the original (a model's delay left in would put every cleaned line late,
silently). Runs the real model on the CPU (1.5 s of audio); skipped where it is not installed."""
import numpy as np
import pytest

# The clean-up models run on onnxruntime, an optional package: without it the test says so and is skipped.
pytest.importorskip("onnxruntime", reason="the optional clean-up package onnxruntime is not installed")
from rostrum_sound.cleanup import models, noise  # noqa: E402


def _have(m):
    try:
        models.path(m)
        return True
    except Exception:  # noqa: BLE001
        return False


def _speechlike(rate, seconds=1.5):
    t = np.arange(int(rate * seconds)) / rate
    env = (np.sin(2 * np.pi * 3 * t) > 0.3).astype(np.float32)          # syllable-like bursts
    voiced = sum(np.sin(2 * np.pi * f * t) / k for k, f in enumerate((140, 280, 420, 560, 700, 1400), 1))
    return (0.2 * env * voiced).astype(np.float32)[None]


@pytest.mark.skipif(not _have(models.DFN3), reason="DeepFilterNet 3 not installed")
def test_denoised_take_is_not_delayed():
    x = _speechlike(noise.RATE)
    y = noise.clean(x, 1.0)
    n = x.shape[1] + y.shape[1] - 1                  # cross-correlation by FFT: index k = lag k, n - k = lag -k
    c = np.fft.irfft(np.fft.rfft(y[0], n) * np.conj(np.fft.rfft(x[0], n)), n)
    assert int(np.argmax(c)) == 0
