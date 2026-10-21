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


def draw_loudness(y, sr, t, st, png, title, limiter=None):
    """`limiter` = (hop seconds, dB reduced per hop, worst moments): a third panel under the other two."""
    fig, axes = plt.subplots(3 if limiter else 2, 1, figsize=(16, 12 if limiter else 9), dpi=100, sharex=True)
    a1, a2 = axes[0], axes[1]
    if limiter:
        hop, red, worst = limiter
        a3 = axes[2]
        a3.fill_between(np.arange(len(red)) * hop, 0, -np.asarray(red), color="#d62728", alpha=0.6, step="mid")
        for w in worst:
            a3.annotate(f"{w['reduced_db']:.1f} dB", (w["time_s"], -w["reduced_db"]), textcoords="offset points",
                        xytext=(0, -14), ha="center", fontsize=11)
        a3.set_ylabel("limiter gain (dB)")
        a3.set_ylim(min(-1.0, -max(red, default=0) * 1.3), 0.3)
        a3.set_xlabel("time (seconds)")
        a2.set_xlabel("")
    a1.plot(t, np.where(st > -70, st, np.nan), lw=3, color="#1f77b4")
    a1.set_ylabel("short-term loudness (LUFS)")
    a1.set_title(title)
    ts, b = band_curves(y, sr)
    for k, (name, _, _) in enumerate(BANDS):
        a2.plot(ts, b[k], lw=2.5, color=BAND_COLORS[k], label=name)
    a2.set_ylabel("band energy (dB)")
    if not limiter:
        a2.set_xlabel("time (seconds)")
    a2.set_ylim(max(-100, np.nanmin(b)), np.nanmax(b) + 3)
    a2.legend(ncol=5, loc="lower center")
    for a in axes:
        a.grid(alpha=0.3)
        a.xaxis.label.set_fontsize(14)
        a.yaxis.label.set_fontsize(14)
        a.tick_params(labelsize=12)
    a1.title.set_fontsize(16)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return str(png)
