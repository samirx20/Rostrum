"""The STFT pair and the multichannel Wiener filter the stem step wraps around its network (Open-Unmix's own
post-processing, written in numpy: torch.stft / istft with center=True and a periodic Hann window; one EM iteration
of the local Gaussian model, Nugraha et al. 2016, as openunmix.filtering does)."""
from __future__ import annotations

import numpy as np


def window(n: int) -> np.ndarray:
    return (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)


def stft(x: np.ndarray, n: int, hop: int) -> np.ndarray:
    """[channels, samples] -> complex [channels, bins, frames]."""
    p = np.pad(x, ((0, 0), (n // 2, n // 2)), mode="reflect")
    frames = 1 + (p.shape[1] - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    return np.fft.rfft(p[:, idx] * window(n), axis=-1).transpose(0, 2, 1).astype(np.complex64)


def istft(X: np.ndarray, n: int, hop: int, length: int) -> np.ndarray:
    """complex [channels, bins, frames] -> [channels, length] (overlap-add, window-squared normalized)."""
    w = window(n)
    frames = X.shape[2]
    y = np.fft.irfft(X.transpose(0, 2, 1), n=n, axis=-1) * w
    total = n + hop * (frames - 1)
    out, norm = np.zeros((X.shape[0], total), np.float64), np.zeros(total)
    for f in range(frames):
        out[:, f * hop:f * hop + n] += y[:, f]
        norm[f * hop:f * hop + n] += w ** 2
    out = out[:, n // 2:n // 2 + length] / np.maximum(norm[n // 2:n // 2 + length], 1e-11)
    return out.astype(np.float32)


def wiener(mags: np.ndarray, mix: np.ndarray, win: int = 300, eps: float = 1e-10) -> np.ndarray:
    """mags [sources, channels, bins, frames] (magnitudes), mix complex [channels, bins, frames] ->
    complex [sources, channels, bins, frames]: the sources with the mix's phase, refined by one EM step per
    window of `win` frames."""
    out = np.zeros(mags.shape, np.complex64)
    for a in range(0, mix.shape[2], win):
        x = mix[:, :, a:a + win].transpose(2, 1, 0).astype(np.complex128)          # [t, f, c]
        v0 = mags[:, :, :, a:a + win].transpose(3, 2, 1, 0).astype(np.float64)     # [t, f, c, j]
        scale = max(1.0, float(np.sqrt(np.abs(x) ** 2).max()) / 10.0)
        x = x / scale
        y = v0 / scale * np.exp(1j * np.angle(x))[..., None]                        # [t, f, c, j]
        v = np.mean(np.abs(y) ** 2, axis=2)                                          # [t, f, j]
        R = np.einsum("tfcj,tfdj->jfcd", y, y.conj()) / (eps + v.sum(0).T)[..., None, None]  # [j, f, c, d]
        C = np.sqrt(eps) * np.eye(2)[None, None] + np.einsum("tfj,jfcd->tfcd", v, R)
        inv = np.linalg.inv(C)
        gain = np.einsum("tfj,jfce,tfed->tfjcd", v, R, inv)
        y = np.einsum("tfjcd,tfd->tfcj", gain, x) * scale
        out[:, :, :, a:a + win] = y.transpose(3, 2, 1, 0)
    return out
