"""The cleanup pictures: before / after spectrograms stacked on one colour scale with each file's level curve, noise
floor and speech level drawn over them; and the stems' levels over time, one row each."""
import matplotlib

matplotlib.use("Agg")
import librosa
import matplotlib.pyplot as plt
import numpy as np

from .cleanup import FRAME_S, frames_db
from .core import load, mono, name_of
from .spectrogram import FMIN, HOP, _stft_db
from .tones import N_FFT

LEVEL_LO = -90.0


def _row(ax, m, sr, ref, facts, title):
    """One spectrogram row (dB under `ref`, the louder file's peak) with the level curve on a right-hand dB axis."""
    S = _stft_db(m)
    f = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    t = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=HOP)
    keep = f >= FMIN
    im = ax.pcolormesh(t, f[keep], 10 * np.log10(np.maximum(S[keep], 1e-20) / ref), shading="auto", cmap="magma",
                       vmin=-90, vmax=0)
    ax.set_yscale("log")
    ax.set_ylim(FMIN, sr / 2)
    ax.set_ylabel("frequency (Hz)", fontsize=13)
    ax.set_title(title, fontsize=15)
    lv = frames_db(m, sr)
    lx = ax.twinx()
    lx.plot((np.arange(len(lv)) + 0.5) * FRAME_S, lv, color="white", lw=1.2, alpha=0.9)
    for key, colour, label in (("floor_db", "cyan", "noise floor"), ("level_db", "lime", "speech level")):
        at = max(facts[key], LEVEL_LO + 1)          # digital silence (-120 dB) is drawn on the bottom edge
        lx.axhline(at, color=colour, lw=2, ls="--")
        lx.text(0.01, at, f" {label} {facts[key]:.1f} dB", color=colour, fontsize=12, va="bottom",
                transform=lx.get_yaxis_transform())
    lx.set_ylim(LEVEL_LO, 0)
    lx.set_ylabel("level (dB, white line)", fontsize=13)
    return im


def draw_compare(before, after, b_facts, a_facts, png) -> str:
    (yb, sr_b), (ya, sr_a) = load(before), load(after)
    mb, ma = mono(yb), mono(ya)
    ref = max(_stft_db(mb).max(), _stft_db(ma).max(), 1e-20)
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), dpi=100, sharex=True)
    _row(axes[0], mb, sr_b, ref, b_facts, f"before: {name_of(before)}  (gap {b_facts['gap_db']} dB)")
    im = _row(axes[1], ma, sr_a, ref, a_facts, f"after: {name_of(after)}  (gap {a_facts['gap_db']} dB)")
    axes[1].set_xlabel("time (seconds)", fontsize=13)
    fig.colorbar(im, ax=axes, label="dB under the louder file's loudest point", pad=0.06)
    fig.savefig(png)
    plt.close(fig)
    return str(png)


def draw_stems(envs: dict, png, title) -> str:
    """envs: {stem: (linear level per 50 ms frame, rate)}; one row per stem, same dB scale."""
    fig, axes = plt.subplots(len(envs), 1, figsize=(16, 2.6 * len(envs)), dpi=100, sharex=True, squeeze=False)
    for ax, (name, (env, _)) in zip(axes[:, 0], envs.items()):
        d = 20 * np.log10(np.maximum(env, 1e-6))
        ax.fill_between((np.arange(len(d)) + 0.5) * FRAME_S, LEVEL_LO, np.maximum(d, LEVEL_LO), color="tab:orange",
                        alpha=0.8)
        ax.set_ylim(LEVEL_LO, 0)
        ax.set_ylabel(f"{name}\n(dB)", fontsize=13)
        ax.grid(alpha=0.3)
    axes[0, 0].set_title(f"stems of {title}: level over time (50 ms)", fontsize=15)
    axes[-1, 0].set_xlabel("time (seconds)", fontsize=13)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return str(png)
