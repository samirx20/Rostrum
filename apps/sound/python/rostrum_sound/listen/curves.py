"""The loudness + band-energy picture (matplotlib, never shown on screen)."""
import matplotlib

matplotlib.use("Agg")
import librosa
import matplotlib.pyplot as plt
import numpy as np

from .core import BANDS, db, mono

BAND_COLORS = ["#4b0082", "#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"]
N_FFT, HOP = 4096, 2048


def band_curves(y, sr, step=0.5):
    """Band energy in dB per `step` seconds -> (times, [5, T])."""
    pw = (np.abs(librosa.stft(mono(y), n_fft=N_FFT, hop_length=HOP)) * 2.0 / np.hanning(N_FFT).sum()) ** 2 / 2.0
    f = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    t = librosa.frames_to_time(np.arange(pw.shape[1]), sr=sr, hop_length=HOP)
    edges = np.arange(0, t[-1] + step, step)
    idx = np.digitize(t, edges) - 1
    ts, rows = [], []
    for i in np.unique(idx):
        sel = idx == i
        ts.append(edges[i] + step / 2)
        rows.append([db(pw[(f >= lo) & ((f < hi) if hi else True)][:, sel].sum(axis=0).mean())
                     for _, lo, hi in BANDS])
    return np.array(ts), np.array(rows).T


def draw_loudness(y, sr, t, st, png, title):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(16, 9), dpi=100, sharex=True)
    a1.plot(t, np.where(st > -70, st, np.nan), lw=3, color="#1f77b4")
    a1.set_ylabel("short-term loudness (LUFS)")
    a1.set_title(title)
    ts, b = band_curves(y, sr)
    for k, (name, _, _) in enumerate(BANDS):
        a2.plot(ts, b[k], lw=2.5, color=BAND_COLORS[k], label=name)
    a2.set_ylabel("band energy (dB)")
    a2.set_xlabel("time (seconds)")
    a2.set_ylim(max(-100, np.nanmin(b)), np.nanmax(b) + 3)
    a2.legend(ncol=5, loc="lower center")
    for a in (a1, a2):
        a.grid(alpha=0.3)
        a.xaxis.label.set_fontsize(14)
        a.yaxis.label.set_fontsize(14)
        a.tick_params(labelsize=12)
    a1.title.set_fontsize(16)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return str(png)
