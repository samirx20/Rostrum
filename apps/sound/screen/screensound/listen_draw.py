"""The Mix page's two listen pictures, drawn for the panel they sit in: wide and short (the panel's shape), dark like
the screen, text at the screen's size once fitted. The numbers are the agent's ears' own (rostrum_sound.listen:
short-term and integrated loudness, energy per band, the spectrum over time); only the drawing is the screen's.
"""
from __future__ import annotations

import numpy as np

from rostrum_sound.listen import bs1770
from rostrum_sound.listen.core import BANDS
from rostrum_sound.listen.curves import band_curves
from rostrum_sound.listen.plot import pyplot
from rostrum_sound.listen.spectrogram import FMIN, over_time

# Theme.qml's colours (sunken well, text, lines, accent) and the bands' colours, light enough for a dark ground.
WELL, FG, FG2, FG3, LINE, ACCENT = "#101010", "#ececec", "#a3a3a3", "#8a8a8a", "#3a3a3a", "#4c8dff"
BAND_COLOURS = ["#b18cff", "#4c8dff", "#4cc38a", "#f2b33d", "#ff6b6b"]
SIZE, DPI = (7.5, 1.5), 200      # 5 : 1 like the panel's slots; drawn at twice the size they're shown, for sharp text
FONTS = ["Segoe UI", "Helvetica Neue", "Helvetica", "DejaVu Sans"]   # the first one this machine has
MAX_COLUMNS = 900                # spectrum columns drawn (more than the slot has pixels)


RC = {"font.size": 11, "text.color": FG2, "axes.labelcolor": FG2, "axes.edgecolor": LINE,
      "xtick.color": FG3, "ytick.color": FG3, "axes.facecolor": WELL, "figure.facecolor": WELL,
      "axes.titlesize": 11.5, "axes.titlecolor": FG, "axes.titlelocation": "left", "legend.frameon": False}


def _rc() -> dict:
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    return {**RC, "font.family": next((f for f in FONTS if f in have), "DejaVu Sans")}


def _figure(plt, cols: int, widths=None):
    fig, axes = plt.subplots(1, cols, figsize=SIZE, dpi=DPI, squeeze=False, gridspec_kw={"width_ratios": widths})
    from matplotlib.ticker import FuncFormatter, MaxNLocator
    for ax in axes[0]:
        ax.tick_params(length=2, pad=2)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=9 if cols == 1 else 5, steps=[1, 2, 5, 10]))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g} s"))
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    return fig, axes[0]


def _save(plt, fig, png) -> str:
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.17, top=0.82, wspace=0.16)
    fig.savefig(png, facecolor=WELL)
    plt.close(fig)
    return str(png)


def loudness_panel(y, sr, t, st, png) -> str:
    """Left: short-term loudness with the integrated level dashed. Right: energy per band over time."""
    plt = pyplot()
    with plt.rc_context(_rc()):
        fig, (a1, a2) = _figure(plt, 2, [1, 1.6])
        whole = bs1770.integrated(y, sr)
        a1.plot(t, np.where(st > -70, st, np.nan), lw=1.6, color=ACCENT)
        if np.isfinite(whole):
            a1.axhline(whole, color=FG2, lw=0.9, ls="--")
            a1.text(t[-1] if len(t) else 0, whole, f"integrated {whole:.1f} ".replace("-", "−"), color=FG2, fontsize=10, ha="right", va="bottom")
        a1.set_title("Short-term loudness (LUFS)")
        ts, b = band_curves(y, sr)
        for k, (name, _, _) in enumerate(BANDS):
            a2.plot(ts, b[k], lw=1.2, color=BAND_COLOURS[k], label=name.replace("_", " "))
        a2.set_ylim(max(-100, np.nanmin(b)), np.nanmax(b) + 3)
        a2.set_title("Bands (dB)")
        a2.legend(ncol=5, loc="lower right", bbox_to_anchor=(1.0, 0.98), fontsize=10, handlelength=0.9, handletextpad=0.4, columnspacing=0.7,
                  borderaxespad=0, labelcolor=FG2)
        for ax in (a1, a2):
            ax.grid(color=LINE, lw=0.5)
            ax.set_xlim(0, max(t[-1] if len(t) else 0, ts[-1] if len(ts) else 0))
        return _save(plt, fig, png)


def spectrum_panel(y, sr, png) -> str:
    """The spectrum over time on a log frequency scale; brighter = louder (dB under the loudest point)."""
    t, f, D, _, (a, b) = over_time(y, sr)
    step = max(1, D.shape[1] // MAX_COLUMNS)
    keep = f >= FMIN
    plt = pyplot()
    with plt.rc_context(_rc()):
        fig, (ax,) = _figure(plt, 1)
        ax.pcolormesh(t[::step], f[keep], D[keep][:, ::step], shading="auto", cmap="magma", vmin=-80, vmax=0,
                      rasterized=True)
        ax.set_yscale("log")
        ticks = [v for v in (100, 1000, 10000) if v < sr / 2]
        ax.set_yticks(ticks, [f"{v // 1000}k" if v >= 1000 else str(v) for v in ticks])
        ax.minorticks_off()
        ax.set_ylim(FMIN, sr / 2)
        ax.set_xlim(a, b)
        ax.set_ylabel("Hz", fontsize=10, labelpad=1)
        ax.set_title("Spectrum over time (brighter = louder)")
        return _save(plt, fig, png)
