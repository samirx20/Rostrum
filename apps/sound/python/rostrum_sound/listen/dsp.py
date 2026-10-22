"""Small numpy signal tools the ears need: STFT, frequencies and times of its bins, dB, note names, frame RMS,
resampling and reading a file at a rate. They replace librosa / SciPy in the shipped app (those pull ~250 MB);
each one computes what the library call it replaces did (same windows, padding and filter), checked against it
on real renders (brief P22: loudness within 0.001 LU, onsets the same frames).
"""
from __future__ import annotations

import math
import os

import numpy as np

CHUNK = 512                     # STFT frames per FFT call (bounds the temporary copy of the frames)
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def hann(n: int) -> np.ndarray:
    """The periodic Hann window (librosa's STFT window)."""
    return (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)


def frames(y: np.ndarray, n: int, hop: int, center: bool = True) -> np.ndarray:
    """[frames, n] views of `y` every `hop` samples; `center` pads n // 2 zeros each side (frame k centred on k * hop)."""
    y = np.asarray(y, np.float32)
    if center:
        y = np.pad(y, n // 2)
    if y.size < n:
        y = np.pad(y, (0, n - y.size))
    return np.lib.stride_tricks.sliding_window_view(y, n)[::hop]


def stft(y: np.ndarray, n_fft: int, hop: int, window: np.ndarray | None = None) -> np.ndarray:
    """Complex STFT [bins, frames] of mono `y`, centred, zero padded (librosa.stft's defaults)."""
    w = hann(n_fft) if window is None else np.asarray(window, np.float32)
    fr = frames(y, n_fft, hop)
    return np.concatenate([np.fft.rfft(fr[i:i + CHUNK] * w, axis=1) for i in range(0, len(fr), CHUNK)]).T


def fft_frequencies(sr: float, n_fft: int) -> np.ndarray:
    return np.fft.rfftfreq(n_fft, 1.0 / sr)


def frames_to_time(k, sr: float, hop: int) -> np.ndarray:
    return np.asarray(k) * hop / float(sr)


def power_to_db(S: np.ndarray, ref: float | None = 1.0, top_db: float | None = 80.0, amin: float = 1e-10) -> np.ndarray:
    """10·log10(S / ref), floored at `amin` and at `top_db` under the loudest value; `ref=None` = the loudest value."""
    ref = float(np.max(S)) if ref is None else ref
    d = 10.0 * np.log10(np.maximum(amin, S)) - 10.0 * math.log10(max(amin, ref))
    return np.maximum(d, d.max() - top_db) if top_db is not None and d.size else d


def hz_to_note(f: float) -> str:
    """440 -> "A4", rounded to the nearest semitone (sharps)."""
    m = int(round(12 * math.log2(f / 440.0) + 69))
    return f"{NOTES[m % 12]}{m // 12 - 1}"


def rms(y: np.ndarray, frame_length: int, hop: int) -> np.ndarray:
    """RMS per centred frame (librosa.feature.rms)."""
    fr = frames(y, frame_length, hop)
    return np.sqrt(np.mean(np.square(fr, dtype=np.float64), axis=1))


def _kaiser_lowpass(up: int, down: int) -> tuple[np.ndarray, int]:
    """SciPy resample_poly's filter: Kaiser (beta 5) windowed sinc, 10 zero crossings per side, gain `up`."""
    rate = max(up, down)
    half = 10 * rate
    m = np.arange(2 * half + 1) - half
    h = np.sinc(m / rate) / rate * np.kaiser(2 * half + 1, 5.0)
    return h / h.sum() * up, half


def resample_poly(x: np.ndarray, up: int, down: int, axis: int = 0) -> np.ndarray:
    """Polyphase resampling by up / down along `axis` (scipy.signal.resample_poly with its default filter, zero
    padded ends): output m = sum_k h[k] · upsampled[m·down + half − k]. Outputs m0, m0 + up, m0 + 2·up … share one
    phase of the filter and read the input every `down` samples, so each phase is one strided window × taps product."""
    g = math.gcd(int(up), int(down))
    up, down = int(up) // g, int(down) // g
    x = np.asarray(x)
    if up == down == 1:
        return x.copy()
    xs = np.moveaxis(x, axis, -1)
    lead = xs.shape[:-1]
    xs = xs.reshape(-1, xs.shape[-1]).astype(np.float64)
    n_in = xs.shape[-1]
    n_out = -(-n_in * up // down)
    h, half = _kaiser_lowpass(up, down)
    taps = -(-h.size // up)
    poly = np.pad(h, (0, taps * up - h.size)).reshape(taps, up).T[:, ::-1]   # poly[r] = h[r + j·up], j reversed
    out = np.empty((xs.shape[0], n_out))
    for c in range(xs.shape[0]):
        win = np.lib.stride_tricks.sliding_window_view(np.pad(xs[c], (taps, 2 * taps + down)), taps)
        for m0 in range(min(up, n_out)):
            p0 = m0 * down + half
            r, q0 = p0 % up, p0 // up
            count = len(range(m0, n_out, up))
            for t in range(0, count, 1 << 16):
                k = min(count, t + (1 << 16))
                out[c, m0 + up * t:m0 + up * k:up] = win[q0 + 1 + down * t:q0 + 1 + down * k:down] @ poly[r]
    out = np.moveaxis(out.reshape(lead + (n_out,)), -1, axis)
    return out.astype(x.dtype) if x.dtype.kind == "f" else out


def resample(y: np.ndarray, sr_from: int, sr_to: int, axis: int = -1) -> np.ndarray:
    return y if sr_from == sr_to else resample_poly(y, int(sr_to), int(sr_from), axis=axis)


def load_mono(path, sr: int) -> np.ndarray:
    """A file's samples, mono, float32, at `sr` Hz (what librosa.load(path, sr=sr, mono=True) gave)."""
    import soundfile as sf
    y, rate = sf.read(os.fspath(path), dtype="float32", always_2d=True)
    return resample(y.mean(axis=1), rate, sr).astype(np.float32)
