"""review's clipped-text fact, read from the document's boxes (review_sample): a text cut by the edge of a box that clips
it (a device's screen, a group with Clip to box or overflow hidden) — its letters partly outside, so a client sees a word
sliced off. A text sliding in or out through the edge (a reveal) passes in under CLIP_S; one wholly outside is hidden, not
cut. Each fault is {kind, start, end, id, ids, text} with times, the layer, the box and a fix."""
from __future__ import annotations

from .geometry import drawn_box
from .review_layout import _glyphs
from .review_sample import Sampled, runs

CUT = (0.04, 0.96)        # a text with this share of its letters' box outside the clipping box is cut (more: hidden)
CLIP_S = 1.0              # for this long or longer (shorter: a reveal or a wipe passing)
SEEN_TEXT = 0.25          # a text this opaque or more


def _outside(box, holder) -> tuple[float, str]:
    """The share of `box` outside `holder` and the side most of it sticks out of."""
    x0, y0, x1, y1 = box
    a, b, c, d = holder
    area = max((x1 - x0) * (y1 - y0), 1e-6)
    w, h = max(0.0, min(x1, c) - max(x0, a)), max(0.0, min(y1, d) - max(y0, b))
    sides = {"left": a - x0, "right": x1 - c, "top": b - y0, "bottom": y1 - d}
    return 1 - w * h / area, max(sides, key=sides.get)


def clipped(s: Sampled) -> list[dict]:
    hits: dict[tuple, dict[int, tuple]] = {}
    for i, (t, nodes) in enumerate(s.frames):
        by = {n["id"]: n for n in nodes}
        for n in nodes:
            if n["type"] != "text" or not s.seen(n) or n["opacity"] < SEEN_TEXT:
                continue
            box = _glyphs(drawn_box(n))
            for g in reversed(n["within"]):                  # the nearest clipping box first
                holder = by.get(g)
                if holder is None or not holder["props"].get("clip"):
                    continue
                share, side = _outside(box, drawn_box(holder))
                if CUT[0] <= share <= CUT[1]:
                    hits.setdefault((n["id"], g), {})[i] = (share, side)
                break
    out = []
    for (tid, g), at in hits.items():
        found = runs([i in at for i in range(len(s.times))], s.times, s.step, CLIP_S)
        if not found:
            continue
        t0, t1, a, b = max(found, key=lambda r: r[1] - r[0])
        share, side = max((at[i] for i in range(a, b + 1)), key=lambda r: r[0])
        out.append({"kind": "text_clipped", "start": t0, "end": t1, "id": tid, "ids": [tid, g], "cut_pct": round(100 * share),
                    "text": f'{t0:g}–{t1:g} s: text "{tid}" is cut by the {side} edge of "{g}" ({100 * share:.0f} % of its letters '
                            f'outside): lay the screen out (column / row inside "{g}") so the text wraps in its room, or move it in'})
    return out


def facts(s: Sampled) -> list[dict]:
    return clipped(s)
