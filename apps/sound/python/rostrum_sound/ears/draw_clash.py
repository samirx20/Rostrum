"""The clash picture: time across, 1/3-octave bands up, each cell coloured by the pair of tracks fighting there."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from .clash import CENTRES

def _label(c):
    c = float(f"{c:.2g}")
    return f"{c / 1000:g}k" if c >= 1000 else f"{c:g}"


PALETTE = ["#d1362f", "#3b6fd4", "#2a9d4b", "#e08a00", "#8e44ad", "#00a3a3", "#b5651d", "#c2185b", "#5d6d7e", "#7cb342"]


def clash_picture(png, maps: dict, spans: list, hop_s: float, title="clashes: both tracks loud in the same band"):
    """`maps` {(a, b): bool [bands, frames]}; pairs with no clash are left out of the legend."""
    pairs = [p for p, m in maps.items() if m.any()]
    shape = next(iter(maps.values())).shape if maps else (len(CENTRES), 1)
    cells = np.zeros(shape, dtype=int)
    for i, p in enumerate(pairs):
        cells[maps[p]] = i + 1
    fig, ax = plt.subplots(figsize=(16, 8), dpi=100)
    cmap = ListedColormap(["#f4f5f7"] + [PALETTE[i % len(PALETTE)] for i in range(len(pairs))])
    ax.imshow(cells, origin="lower", aspect="auto", cmap=cmap, vmin=0, vmax=max(len(pairs), 1), interpolation="nearest",
              extent=(0, shape[1] * hop_s, -0.5, shape[0] - 0.5))
    ticks = list(range(0, len(CENTRES), 3))
    ax.set_yticks(ticks)
    ax.set_yticklabels([_label(CENTRES[k]) for k in ticks], fontsize=13)
    ax.tick_params(axis="x", labelsize=14)
    ax.set_xlabel("time (seconds)", fontsize=16)
    ax.set_ylabel("band centre (Hz)", fontsize=16)
    ax.set_title(title if pairs else "no clashes found", fontsize=17)
    if pairs:
        ax.legend(handles=[Patch(color=PALETTE[i % len(PALETTE)], label=f"{a} + {b}") for i, (a, b) in enumerate(pairs)],
                  fontsize=13, loc="upper right", framealpha=0.95)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return str(png)
