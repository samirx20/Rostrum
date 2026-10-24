"""The arrangement picture: one row per track across time (notes as bars placed by pitch inside the row, drum hits
as ticks, clips as boxes, spoken lines as flags), bar lines, sections shaded and named, markers as labelled lines."""
from __future__ import annotations

from ..listen.plot import pyplot
from .draw_clash import PALETTE


def arrangement_picture(png, arr: dict, start: float = 0.0, end: float | None = None, title: str = "arrangement"):
    end = arr["end"] if end is None else end
    rows = arr["tracks"]
    plt = pyplot()
    fig, ax = plt.subplots(figsize=(16, 1.2 + 0.9 * max(len(rows), 1)), dpi=100)
    n = len(rows)
    for name, s, e in arr["sections"]:
        ax.axvspan(s, e, color="#eef1f6", zorder=0)
        ax.text(s, n + 0.05, name, fontsize=9, color="#556", va="bottom")
    for i, b in enumerate(arr["bars"]):
        if start <= b <= end:
            ax.axvline(b, color="#dde", lw=0.6, zorder=1)
            ax.text(b, -0.08, str(i + 1), fontsize=7, color="#99a", ha="center", va="top")
    for r, t in enumerate(rows):
        y0, col = n - 1 - r, PALETTE[r % len(PALETTE)]
        ax.axhline(y0, color="#e4e6ea", lw=0.6)
        ms = [m for _, _, m, _ in t["notes"]]
        lo, hi = (min(ms), max(ms)) if ms else (0, 1)
        span = max(hi - lo, 12)
        for s, e, m, v in t["notes"]:
            y = y0 + 0.1 + 0.75 * (m - lo) / span
            ax.add_patch(plt.Rectangle((s, y), max(e - s, 0.02), 0.06, color=col, alpha=0.35 + 0.65 * min(v, 1), zorder=3))
        drums = sorted({d for _, d in t["hits"]})
        for s, d in t["hits"]:
            y = y0 + 0.1 + 0.8 * (drums.index(d) + 0.5) / len(drums)
            ax.plot([s, s], [y - 0.05, y + 0.05], color=col, lw=1.2, zorder=3)
        for s, e in t["clips"]:
            ax.add_patch(plt.Rectangle((s, y0 + 0.15), e - s, 0.7, fill=False, ec=col, lw=1.2, zorder=3))
        for s, text in t["lines"]:
            ax.text(s, y0 + 0.5, "▸" + text, fontsize=7, color=col, va="center", zorder=3)
        label = t["id"] + (f"  ({', '.join(drums)})" if drums and len(drums) <= 6 else "")
        ax.text(start, y0 + 0.92, label, fontsize=9, color=col, va="top", fontweight="bold", zorder=4)
    for name, at in arr["markers"]:
        if start <= at <= end:
            ax.axvline(at, color="#d1362f", lw=1.4, zorder=5)
            ax.text(at, n + 0.05, f"{name} {at:.2f}s", fontsize=9, color="#d1362f", rotation=0, va="bottom", ha="left")
    ax.set_xlim(start, end)
    ax.set_ylim(-0.3, n + 0.5)
    ax.set_yticks([])
    ax.set_xlabel("seconds (bar numbers under the rows)")
    ax.set_title(title, loc="left", pad=18)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return png
