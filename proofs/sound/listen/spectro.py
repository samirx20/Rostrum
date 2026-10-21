"""spectrogram: log-frequency picture a vision model can read."""
import matplotlib

matplotlib.use("Agg")
import librosa
import matplotlib.pyplot as plt
import numpy as np

from .core import duration, load, mono

FMIN = 30.0


def draw(ax, y, sr, marks=(), mel=False, vmin=None, title=None):
    """Draw a spectrogram on `ax`. Colour = dB below the loudest point."""
    m = mono(y)
    n_fft, hop = 4096, 1024
    S = np.abs(librosa.stft(m, n_fft=n_fft, hop_length=hop)) ** 2
    if mel:
        S = librosa.feature.melspectrogram(S=S, sr=sr, n_mels=128, fmax=sr / 2)
        f = librosa.mel_frequencies(n_mels=128, fmax=sr / 2)
    else:
        f = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    t = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=hop)
    D = librosa.power_to_db(S, ref=np.max, top_db=80)
    keep = f >= FMIN
    im = ax.pcolormesh(t, f[keep], D[keep], shading="auto", cmap="magma",
                       vmin=vmin if vmin is not None else -80, vmax=0)
    ax.set_yscale("log")
    ticks = [t_ for t_ in (50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000) if t_ < sr / 2]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{t_ // 1000}k" if t_ >= 1000 else str(t_) for t_ in ticks])
    ax.set_ylim(FMIN, sr / 2)
    ax.set_xlim(0, duration(y, sr))
    ax.set_xlabel("time (seconds)", fontsize=16)
    ax.set_ylabel("frequency (Hz)", fontsize=16)
    ax.tick_params(labelsize=14)
    for x in marks:
        ax.axvline(x, color="cyan", lw=2, alpha=0.9)
        ax.text(x, sr / 2 * 0.9, f" {x:g}s", color="cyan", fontsize=14, va="top")
    if title:
        ax.set_title(title, fontsize=18)
    return im


def make(path, png, marks=(), mel=False):
    y, sr = load(path)
    fig, ax = plt.subplots(figsize=(16, 8), dpi=100)
    im = draw(ax, y, sr, marks, mel, title=f"{path.replace(chr(92), '/').split('/')[-1]}  (colour: dB below loudest point)")
    fig.colorbar(im, ax=ax, label="dB").ax.tick_params(labelsize=14)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return {"png": png, "size_px": [1600, 800], "marks_s": list(marks), "scale": "mel" if mel else "log-frequency"}
