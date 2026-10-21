"""Shared plotting for compare and report: loudness and band-energy curves."""
import matplotlib

matplotlib.use("Agg")
import numpy as np

from .core import BAND_NAMES, band_power, db
from .loudness import short_term

COLORS = ["#1f77b4", "#d62728"]
BAND_COLORS = ["#4b0082", "#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"]


def band_curves(y, sr, step=0.5):
    """Band energy in dB, averaged per `step` seconds -> (times, [5, T])."""
    times, pw = band_power(y, sr)
    edges = np.arange(0, times[-1] + step, step)
    idx = np.digitize(times, edges) - 1
    ts, rows = [], []
    for i in np.unique(idx):
        ts.append(edges[i] + step / 2)
        rows.append([db(v) for v in pw[:, idx == i].mean(axis=1)])
    return np.array(ts), np.array(rows).T


def plot_loudness(ax, series):
    """series: [(label, y, sr)] -> short-term LUFS lines on ax."""
    for k, (label, y, sr) in enumerate(series):
        t, v = short_term(y, sr)
        ax.plot(t, np.where(v > -70, v, np.nan), lw=3, color=COLORS[k % 2], label=label)
    ax.set_ylabel("short-term loudness (LUFS)", fontsize=16)
    ax.set_xlabel("time (seconds)", fontsize=16)
    ax.tick_params(labelsize=14)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=14)


def plot_bands(ax, y, sr):
    t, b = band_curves(y, sr)
    for k, name in enumerate(BAND_NAMES):
        ax.plot(t, b[k], lw=2.5, color=BAND_COLORS[k], label=name)
    ax.set_ylabel("band energy (dB)", fontsize=16)
    ax.set_xlabel("time (seconds)", fontsize=16)
    ax.set_ylim(max(-100, np.nanmin(b)), np.nanmax(b) + 3)
    ax.tick_params(labelsize=14)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=14, ncol=5, loc="lower center")
