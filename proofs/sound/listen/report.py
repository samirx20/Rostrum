"""report: everything about one WAV in a single call."""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import bands, loudness, onsets, spectro, stereo
from .core import load
from .curves import plot_bands, plot_loudness


def analyse(wav, outdir, section_s=5.0):
    os.makedirs(outdir, exist_ok=True)
    y, sr = load(wav)
    spec = spectro.make(wav, os.path.join(outdir, "spectrogram.png"))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(16, 10), dpi=100)
    plot_loudness(a1, [(os.path.basename(wav), y, sr)])
    plot_bands(a2, y, sr)
    fig.tight_layout()
    curves = os.path.join(outdir, "curves.png")
    fig.savefig(curves)
    plt.close(fig)
    out = {"file": wav, "sample_rate": sr, "channels": y.shape[1],
           "loudness": loudness.analyse(y, sr), "onsets": onsets.analyse(wav),
           "bands": bands.analyse(y, section_s, sr), "stereo": stereo.analyse(y, section_s, sr),
           "images": {"spectrogram": spec["png"], "curves": curves}}
    path = os.path.join(outdir, "report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    out["report_json"] = path
    return out
