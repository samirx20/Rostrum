"""spectrogram: a marked, labelled picture, plus the steady tones found in it and which of them are hum (tones.py)."""
import numpy as np

from .core import duration, load, mono, name_of, num
from .dsp import fft_frequencies, frames_to_time, power_to_db, stft
from .memo import remembered
from .plot import pyplot
from .tones import N_FFT, steady_tones

FMIN = 30.0
HOP = 1024


def _stft_db(m):
    S = np.abs(stft(m, N_FFT, HOP)) ** 2
    return S


def over_time(y, sr, range=None):
    """The numbers every spectrum picture draws -> (times s, frequencies Hz, dB under the loudest point [bins, frames],
    power [bins, frames], (a, b)). `range` (a, b) keeps only that time span."""
    m = mono(y)
    dur = duration(y, sr)
    a, b = (0.0, dur) if range is None else (float(range[0]), float(range[1]))
    if not 0 <= a < b <= dur + 1e-6:
        raise ValueError(f"spectrogram: range {range} is outside the file (0 to {dur:.3f} s)")
    S = _stft_db(m[int(a * sr):int(b * sr)])
    f = fft_frequencies(sr, N_FFT)
    t = a + frames_to_time(np.arange(S.shape[1]), sr, HOP)
    return t, f, power_to_db(S, ref=None, top_db=80), S, (a, b)


@remembered
def spectrogram(wav, out_png, marks=None, range=None):
    """Writes a log-frequency spectrogram PNG (axes: seconds, Hz; colour: dB under the loudest point).
    `marks` {label: time_s} draws labelled cyan lines; `range` (a, b) shows only that time span.
    Facts: the png path, `tones` (every steady narrow line, with its note name and why it is or isn't hum)
    and `hum_lines` (the tones that are hum: flat level, and part of a mains series: two or more multiples of 50 or 60 Hz together)."""
    y, sr = load(wav)
    t, f, D, S, (a, b) = over_time(y, sr, range)
    keep = f >= FMIN
    tones = steady_tones(S, sr)
    plt = pyplot()
    fig, ax = plt.subplots(figsize=(16, 8), dpi=100)
    im = ax.pcolormesh(t, f[keep], D[keep], shading="auto", cmap="magma", vmin=-80, vmax=0)
    ax.set_yscale("log")
    ticks = [v for v in (50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000) if v < sr / 2]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{v // 1000}k" if v >= 1000 else str(v) for v in ticks])
    ax.set_ylim(FMIN, sr / 2)
    ax.set_xlim(a, b)
    ax.set_xlabel("time (seconds)", fontsize=16)
    ax.set_ylabel("frequency (Hz)", fontsize=16)
    ax.tick_params(labelsize=14)
    ax.set_title(f"{name_of(wav)}  (colour: dB under the loudest point)", fontsize=18)
    for label, x in (marks or {}).items():
        if a <= x <= b:
            ax.axvline(x, color="cyan", lw=2, alpha=0.9)
            ax.text(x, sr / 2 * 0.9, f" {label} {x:g}s", color="cyan", fontsize=13, va="top")
    fig.colorbar(im, ax=ax, label="dB").ax.tick_params(labelsize=14)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    return {"png": str(out_png), "range_s": [num(a, 3), num(b, 3)],
            "marks_s": {k: v for k, v in (marks or {}).items()}, "tones": tones, "hum_lines": [t for t in tones if t["is_hum"]],
            "note": "tones: narrow lines standing 12 dB over their neighbours in 80% of frames (held notes and hum); "
                    "hum_lines: those whose level is flat (under 3 dB spread) and that sit on two or more multiples of 50 or "
                    "60 Hz together; a lone steady line, such as a held bass note, is a tone, not hum"}
