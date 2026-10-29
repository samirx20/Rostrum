"""review's clipped-text fact, read from the document's boxes (review_sample): a text cut by the edge of a box that clips
it (a device's screen, a group with Clip to box or overflow hidden) — its letters partly outside, so a client sees a word
sliced off. A text sliding in or out through the edge (a reveal) passes in under CLIP_S; one wholly outside is hidden, not
cut. Each fault is {kind, start, end, id, ids, text} with times, the layer, the box and a fix.

And its spilled-text fact: a text that runs out of a laid-out group (row / column / grid / stack, a card) given a fixed
w or h too small for its words, the group not clipping. The layout puts the words where they need to be, past the
group's box, so they hang out of the card or under the next block (Gemini Argon r2: card(h=190) whose two-line value
ran 49 px below its box, under the panel placed after it). Left out, w / h fit what is inside. A device's screen is
screen_spill's (review_spill), not named here."""
from __future__ import annotations

from .geometry import drawn_box
from .review_device import devices
from .review_layout import _glyphs
from .review_sample import Sampled, runs

CUT = (0.04, 0.96)        # a text with this share of its letters' box outside the clipping box is cut (more: hidden)
SPILL_PX = 4.0            # a text's letters this far past its fixed-size group's edge spill out of it
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
                            f'outside)'})
    return out


def _fixed(n: dict) -> tuple[bool, bool]:
    """(w fixed, h fixed): a laid-out group whose own w / h is set, not fitting what is inside (nor fill / percent)."""
    p = n["props"]
    if n["type"] != "group" or p.get("layout", "none") == "none" or p.get("clip"):
        return False, False
    return p.get("sizeW") == "fixed", p.get("sizeH") == "fixed"


def _needed(nodes: list[dict], g: str, side: str, scale: float) -> tuple[float, int]:
    """(the group's own w or h, the w or h its laid-out layers take: their furthest box past `side`, with its padding)."""
    holder = next(n for n in nodes if n["id"] == g)
    p, f = holder["props"], "w" if side in ("left", "right") else "h"
    a, b, c, d = drawn_box(holder)
    k = {"left": 0, "top": 1, "right": 2, "bottom": 3}[side]
    edge = (min if k < 2 else max)([drawn_box(n)[k] for n in nodes if g in n["within"]] + [(a, b, c, d)[k]])
    pad = p.get("paddingX" if f == "w" else "paddingY", -1)
    pad = pad if pad >= 0 else p.get("padding", 0)
    return p[f], int(p[f] + abs(edge - (a, b, c, d)[k]) / scale + pad + 0.999)


def spilled(s: Sampled) -> list[dict]:
    hits: dict[tuple, dict[int, tuple]] = {}         # (text, group) -> {frame index: (side, px past, scale)}
    screens = {f"{d}_screen" for d in devices(s.comp)}
    for i, (t, nodes) in enumerate(s.frames):
        by = {n["id"]: n for n in nodes}
        for n in nodes:
            if n["type"] != "text" or not s.seen(n) or n["opacity"] < SEEN_TEXT:
                continue
            x0, y0, x1, y1 = _glyphs(drawn_box(n))
            for g in reversed(n["within"]):              # the nearest group with a fixed size the text runs out of
                holder = by.get(g)
                fw, fh = _fixed(holder) if holder and g not in screens else (False, False)
                if not (fw or fh):
                    continue
                a, b, c, d = drawn_box(holder)
                past = {k: v for k, v in (("left", a - x0), ("right", x1 - c), ("top", b - y0), ("bottom", y1 - d))
                        if (fw if k in ("left", "right") else fh)}
                side = max(past, key=past.get)
                if past[side] > SPILL_PX:
                    own = holder["size"][0 if side in ("left", "right") else 1] or 1.0
                    hits.setdefault((n["id"], g), {})[i] = (side, past[side], ((c - a) if side in ("left", "right") else (d - b)) / own)
                break
    out, named = [], set()
    for (tid, g), at in sorted(hits.items(), key=lambda kv: -max(v[1] for v in kv[1].values())):
        found = runs([i in at for i in range(len(s.times))], s.times, s.step, CLIP_S)
        if not found or g in named:                  # one row a group: its worst text
            continue
        named.add(g)
        t0, t1, a, b = max(found, key=lambda r: r[1] - r[0])
        side, px, scale = max((at[i] for i in range(a, b + 1)), key=lambda r: r[1])
        f = "w" if side in ("left", "right") else "h"
        own, need = _needed(s.frames[a][1], g, side, scale or 1.0)
        bigger = "wider" if f == "w" else "taller"
        out.append({"kind": "text_spill", "start": t0, "end": t1, "id": g, "ids": [g, tid], "spill_px": round(px),
                    "text": f'{t0:g}–{t1:g} s: text "{tid}" runs {px:.0f} px out of the {side} of "{g}", whose {f}={own:g} '
                            f'is too small for its words: make "{g}" {bigger} ({f}={need} or more) or leave {f} out so it fits its text'})
    return out


def facts(s: Sampled) -> list[dict]:
    return clipped(s) + spilled(s)
