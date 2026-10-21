"""spectrogram: a marked, labelled picture, plus the steady hum lines found in it."""
import matplotlib

matplotlib.use("Agg")
import librosa
import matplotlib.pyplot as plt
import numpy as np

from .core import duration, load, mono, name_of, num

FMIN = 30.0
N_FFT, HOP = 4096, 1024
HUM_MIN_HZ, HUM_MAX_HZ = 40.0, 1200.0
HUM_PROMINENCE_DB = 12.0     # a line this far above its neighbours...
HUM_STEADY = 0.8             # ...in at least this share of the frames


def _stft_db(m):
    S = np.abs(librosa.stft(m, n_fft=N_FFT, hop_length=HOP)) ** 2
    return S


def hum_lines(S, sr, max_lines=6):
    """Steady narrow lines: bins that stand HUM_PROMINENCE_DB over the bins around them, in
    most frames -> [{freq_hz, strength_db, steady_pct}] strongest first."""
    f = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    sel = (f >= HUM_MIN_HZ) & (f <= HUM_MAX_HZ)
    D = 10 * np.log10(np.maximum(S[sel], 1e-20))
    ff = f[sel]
    k = 8                                                   # neighbour bins each side
    pad = np.pad(D, ((k, k), (0, 0)), mode="edge")
    around = np.median(np.stack([pad[i:i + D.shape[0]] for i in range(0, 2 * k + 1) if i != k]), axis=0)
    lift = D - around
    steady = (lift >= HUM_PROMINENCE_DB).mean(axis=1)
    strength = np.median(lift, axis=1)
    cand = [i for i in range(len(ff)) if steady[i] >= HUM_STEADY
            and (i == 0 or strength[i] >= strength[i - 1]) and (i == len(ff) - 1 or strength[i] >= strength[i + 1])]
    cand.sort(key=lambda i: -strength[i])
    return [{"freq_hz": num(ff[i], 1), "strength_db": num(strength[i], 1), "steady_pct": num(100 * steady[i], 0)}
            for i in cand[:max_lines]]


def spectrogram(wav, out_png, marks=None, range=None):
    """Writes a log-frequency spectrogram PNG (axes: seconds, Hz; colour: dB under the loudest point).
    `marks` {label: time_s} draws labelled cyan lines; `range` (a, b) shows only that time span.
    Facts: the png path and `hum_lines` (steady lines, e.g. mains hum on a bed)."""
    y, sr = load(wav)
    m = mono(y)
    dur = duration(y, sr)
    a, b = (0.0, dur) if range is None else (float(range[0]), float(range[1]))
    if not 0 <= a < b <= dur + 1e-6:
        raise ValueError(f"spectrogram: range {range} is outside the file (0 to {dur:.3f} s)")
    S = _stft_db(m[int(a * sr):int(b * sr)])
    f = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    t = a + librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=HOP)
    D = librosa.power_to_db(S, ref=np.max, top_db=80)
    keep = f >= FMIN
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
            "marks_s": {k: v for k, v in (marks or {}).items()}, "hum_lines": hum_lines(S, sr),
            "note": "hum_lines: narrow lines standing 12 dB over their neighbours in 80% of frames; "
                    "strength_db is the median lift"}
