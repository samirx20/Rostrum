"""Letters as pen strokes (paint.letters, ops_paint_letters.py): words laid out as the centre lines a hand writes them
with, from single-stroke fonts (lettering_fonts/, the Hershey fonts: public domain, NOTICE.md there), each letter's
strokes in the order its font draws them. Painted with any brush they are real strokes, so Drawn so far (write_on.py)
writes them on stroke by stroke, the pen moving at one speed, and every brush setting (taper, swell, pool, wobble,
dry brush) applies.

Sizes are composition px: `size` is the capital height; the first line's baseline starts at (x, y), or sits on
`path` (SVG path data in composition px), the letters bending with it from `start` px along it. `hand` (0..1) is how
unsteady the hand is: each letter a little moved, turned and sized, every line drifting smoothly, from `seed`.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import pathdata

_DIR = Path(__file__).with_name("lettering_fonts")
FONTS = {   # the name agents and people pick -> its file
    "script": "scripts", "script heavy": "scriptc", "cursive": "cursive", "sans": "futural", "sans heavy": "futuram",
    "serif": "rowmans", "serif heavy": "rowmand", "italic": "timesi", "blackletter": "gothiceng",
    "blackletter italic": "gothicita",
}
ALIGN = ("left", "center", "right")


@lru_cache(maxsize=None)
def font(name: str) -> tuple[dict, float, float]:
    """(char -> (left, right, strokes in font units), cap line, base line). A font has ASCII 32..126, one per line."""
    if name not in FONTS:
        raise ValueError(f'font "{name}": not a lettering font; one of {", ".join(FONTS)}')
    lines = (_DIR / f"{FONTS[name]}.jhf").read_text(encoding="ascii").splitlines()
    head = json.loads(lines[0][1:])
    glyphs = {}
    for code, line in enumerate(lines[1:], start=32):
        pairs = [line[i:i + 2] for i in range(8, len(line) - 1, 2)]
        left, right = ord(pairs[0][0]) - 82, ord(pairs[0][1]) - 82
        strokes, cur = [], []
        for p in pairs[1:]:
            if p == " R":
                strokes, cur = strokes + [cur] if len(cur) > 1 else strokes, []
            else:
                cur.append((ord(p[0]) - 82, ord(p[1]) - 82))
        if len(cur) > 1:
            strokes.append(cur)
        glyphs[chr(code)] = (left, right, strokes)
    return glyphs, float(head["define_cap_line"]), float(head["define_base_line"])


def _smooth(pts: np.ndarray, corner: float = 70.0) -> np.ndarray:
    """One corner-cutting pass that keeps the ends and every sharp turn (over `corner` degrees): a font's polygon curves
    round off as a pen draws them, its deliberate points stay points."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b = pts[i] - pts[i - 1], pts[i + 1] - pts[i]
        na, nb = np.hypot(*a), np.hypot(*b)
        turn = math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b) / (na * nb))))) if na and nb else 180.0
        if turn > corner:
            out += [pts[i] - a * 0.25 if na else pts[i], pts[i], pts[i] + b * 0.25 if nb else pts[i]]
        else:
            out += [pts[i] - a * 0.25, pts[i] + b * 0.25]
    out.append(pts[-1])
    return np.asarray(out)


def _dense(pts: np.ndarray, step: float) -> np.ndarray:
    """Points no further apart than `step` px, so a path or a hand's drift bends straight runs too."""
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.ceil(np.hypot(*(b - a)) / step)))
        out += [a + (b - a) * k / n for k in range(1, n + 1)]
    return np.asarray(out)


class _Along:
    """A polyline of `d` (composition px) by length: where a point `u` px along it lies, and its left-hand normal."""

    def __init__(self, d: str):
        pts = []
        for c in pathdata.commands(pathdata.normalize(d)):
            if c[0] in ("M", "L"):
                pts.append(c[1:3])
            elif c[0] == "C":
                p0 = np.asarray(pts[-1], float)
                p1, p2, p3 = (np.asarray(c[i:i + 2], float) for i in (1, 3, 5))
                for t in np.linspace(0, 1, 33)[1:]:
                    pts.append(tuple((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3))
        self.p = np.asarray(pts, float)
        if len(self.p) < 2:
            raise ValueError("path: needs at least two points for the letters to sit on")
        self.s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(self.p, axis=0).T))])

    def place(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        i = np.clip(np.searchsorted(self.s, u) - 1, 0, len(self.s) - 2)
        seg = self.p[i + 1] - self.p[i]
        ln = np.maximum(np.hypot(seg[:, 0], seg[:, 1]), 1e-9)
        tan = seg / ln[:, None]
        base = self.p[i] + tan * (u - self.s[i])[:, None]       # past either end it carries on straight
        return base + np.stack([-tan[:, 1], tan[:, 0]], axis=1) * v[:, None]     # v < 0: above the path


def strokes(text: str, *, font_name: str = "script", size: float = 120.0, x: float = 0.0, y: float = 0.0,
            align: str = "left", spacing: float = 0.0, line: float = 1.6, slant: float = 0.0, hand: float = 0.0,
            seed: int = 0, path: str = "", start: float = 0.0) -> list[list[list[float]]]:
    """The strokes that write `text`, in writing order, each [[x, y], …] in composition px. Fails loudly on a letter the
    font has no stroke for."""
    if not text.strip():
        raise ValueError("text: nothing to write")
    if size <= 0:
        raise ValueError(f"size: the capital height must be above 0 px (got {size})")
    if align not in ALIGN:
        raise ValueError(f'align "{align}": one of {", ".join(ALIGN)}')
    glyphs, cap, base = font(font_name)
    missing = sorted({c for c in text if c != "\n" and c not in glyphs})
    if missing:
        raise ValueError(f"text: the lettering fonts have no strokes for {' '.join(repr(c) for c in missing)} "
                         "(they write the plain English letters, digits and punctuation)")
    k, rng, shear = size / (base - cap), np.random.default_rng(int(seed)), math.tan(math.radians(slant))
    along = _Along(path) if path else None
    out = []
    for row, words in enumerate(text.split("\n")):
        width = sum((glyphs[c][1] - glyphs[c][0]) * k + spacing for c in words) - (spacing if words else 0.0)
        pen = {"left": 0.0, "center": -width / 2, "right": -width}[align]
        drift = rng.uniform(0, 2 * math.pi, 4)         # the line's slow drift: two waves each way, from the seed
        for c in words:
            left, right, glyph = glyphs[c]
            adv = (right - left) * k
            turn, grow = rng.normal(0, 4.0 * hand), 1.0 + rng.normal(0, 0.05 * hand)
            nudge = rng.normal(0, 0.035 * hand * size, 2)
            cx = pen + adv / 2
            for st in glyph:
                p = np.asarray([((gx - left) * k + pen, (gy - base) * k) for gx, gy in st], float)
                p = _dense(_smooth(p), max(size / 24, 1.0))
                a, (cs, sn) = p - (cx, 0.0), (math.cos(math.radians(turn)), math.sin(math.radians(turn)))
                p = np.stack([cs * a[:, 0] - sn * a[:, 1], sn * a[:, 0] + cs * a[:, 1]], 1) * grow + (cx, 0.0) + nudge
                w = p[:, 0] / max(size, 1.0)
                p[:, 1] += hand * size * 0.04 * (np.sin(w * 0.9 + drift[0]) + 0.5 * np.sin(w * 2.3 + drift[1]))
                p[:, 0] += hand * size * 0.02 * (np.sin(w * 1.3 + drift[2]) + 0.5 * np.sin(w * 3.1 + drift[3]))
                p[:, 0] -= p[:, 1] * shear
                p[:, 1] += row * line * size
                if along is not None:
                    p = along.place(p[:, 0] + start, p[:, 1])
                else:
                    p += (x, y)
                out.append([[round(float(a), 2), round(float(b), 2)] for a, b in p])
            pen += adv + spacing
    return out
