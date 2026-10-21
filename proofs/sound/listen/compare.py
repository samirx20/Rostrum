"""compare: two files side by side - spectrograms, loudness curves, band balance."""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import bands, loudness, spectro
from .core import BAND_NAMES, load
from .curves import plot_loudness


def analyse(a, b, png):
    (ya, sra), (yb, srb) = load(a), load(b)
    na, nb = os.path.basename(a), os.path.basename(b)
    la, lb = loudness.analyse(ya, sra), loudness.analyse(yb, srb)
    ba, bb = bands.analyse(ya, 1e9, sra), bands.analyse(yb, 1e9, srb)
    whole = lambda r: r["sections"][0]["db"]
    table = {n: {"a_db": whole(ba)[n], "b_db": whole(bb)[n],
                 "b_minus_a_db": None if None in (whole(ba)[n], whole(bb)[n])
                 else round(whole(bb)[n] - whole(ba)[n], 1)} for n in BAND_NAMES}
    fig = plt.figure(figsize=(16, 16), dpi=100)
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.9], width_ratios=[1, 0.01], hspace=0.4)
    spectro.draw(fig.add_subplot(gs[0, 0]), ya, sra, title=f"A: {na}")
    spectro.draw(fig.add_subplot(gs[1, 0]), yb, srb, title=f"B: {nb}")
    plot_loudness(fig.add_subplot(gs[2, 0]), [(f"A: {na}", ya, sra), (f"B: {nb}", yb, srb)])
    fig.savefig(png, bbox_inches="tight")
    plt.close(fig)
    pick = lambda r: {k: r[k] for k in ("duration_s", "integrated_lufs", "true_peak_dbtp", "lra_lu", "rms_dbfs")}
    return {"png": png, "a": {"file": na, **pick(la)}, "b": {"file": nb, **pick(lb)},
            "band_balance_whole_file": table,
            "note": "spectrograms are each scaled to their own loudest point; loudness curves share one axis"}
