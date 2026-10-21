"""Text layers → Lottie shape layers made of glyph outlines (fontTools, MIT), grouped per text layer.

Why outlines and not a Lottie text layer (ty 5): a ty 5 layer needs the font on the viewer's machine (or a font asset),
and lottie-web, Skottie and rlottie each lay it out differently; outlines are plain bezier shapes that every player
draws the same. The layer keeps its transform, opacity, blend, masks, colour keys and gradient like any other layer.

Layout: the engine only measures a text's box (textsize.py); the glyph positions are not reachable from Python. So this
module lays the glyphs out itself: the font's own advance widths (at the weight / width / optical size the text asks
for), `tracking`, `lineHeight`, line breaks, wrapping at `boxWidth`, `align`; baseline from the font's ascent / descent
(CSS line box). Kerning, ligatures, small caps, figure styles and OpenType `features` are NOT applied (reported). When
the engine is built, its box is used for the layer's box and the report says how far our line lengths are from it.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from .. import textsize
from .lottie_layer import common
from .lottie_props import Ctx, build, frozen, rgb
from .lottie_shapes import _STILL, _stroke, gradient, group

FONTS = Path(__file__).resolve().parents[3] / "engine" / "fonts"
HELD = ["body", "font", "size", "weight", "stretch", "tracking", "lineHeight", "align", "boxWidth", "slant", "grade", "stroke"]
UNDONE = {"ligatures": True, "smallCaps": False, "figures": "default", "features": "", "axes": ""}


class _Pen(BasePen):
    """Outline → Lottie bezier contours (y flipped, scaled, moved to the glyph's pen position)."""

    def __init__(self, gs, k: float, dx: float, dy: float):
        super().__init__(gs)
        self.k, self.dx, self.dy, self.out, self.cur = k, dx, dy, [], None

    def _p(self, pt):
        return [self.dx + pt[0] * self.k, self.dy - pt[1] * self.k]

    def _moveTo(self, pt):
        self.cur = {"c": True, "v": [self._p(pt)], "i": [[0, 0]], "o": [[0, 0]]}

    def _lineTo(self, pt):
        self._curveToOne(self._getCurrentPoint(), pt, pt)

    def _curveToOne(self, a, b, c):
        s = self.cur
        v = s["v"][-1]
        s["o"][-1] = [self._p(a)[0] - v[0], self._p(a)[1] - v[1]]
        q = self._p(c)
        s["v"].append(q)
        s["i"].append([self._p(b)[0] - q[0], self._p(b)[1] - q[1]])
        s["o"].append([0, 0])

    def _closePath(self):
        s = self.cur
        if len(s["v"]) > 1 and s["v"][-1] == s["v"][0]:      # the last point lands on the first: close, don't repeat it
            s["i"][0] = s["i"].pop()
            s["v"].pop()
            s["o"].pop()
        self.out.append(s)

    _endPath = _closePath


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Path]:
    """Family name → font file, as the engine lists them (each family, also without a trailing " Variable")."""
    folder = Path(os.environ.get("ROSTRUM2D_FONTS", FONTS))
    found = {}
    for path in sorted(folder.glob("*.[ot]tf")):
        names = TTFont(path, lazy=True)["name"]
        for nid in (16, 1):
            fam = names.getDebugName(nid)
            if fam:
                found.setdefault(fam, path)
                found.setdefault(re.sub(r" Variable$", "", fam), path)
    return found


@lru_cache(maxsize=16)
def _font(path: Path) -> TTFont:
    return TTFont(path)


def _location(font: TTFont, p: dict, axes: str) -> tuple:
    """The variable axes the text asks for, held to each axis's range (as the engine does, as CSS)."""
    want = {"wght": p["weight"], "wdth": p["stretch"], "opsz": min(max(p["size"], 8), 144)}
    if p["slant"]:
        want["slnt"] = p["slant"]
    if p["grade"]:
        want["GRAD"] = p["grade"]
    want.update({t: float(v) for t, v in re.findall(r"(\w{4})\s+(-?[\d.]+)", axes)})
    ax = {a.axisTag: a for a in font["fvar"].axes} if "fvar" in font else {}
    return tuple(sorted((t, min(max(v, ax[t].minValue), ax[t].maxValue)) for t, v in want.items() if t in ax))


def _lines(p: dict, gs, cmap: dict, k: float, lost: set) -> list[tuple[list, float]]:
    """[(glyph names with their pen x, line width)] per line: breaks at a new line, wrapped at boxWidth when it is set."""
    adv = lambda ch: gs[cmap[ord(ch)]].width * k + p["tracking"] * p["size"]  # noqa: E731
    lines = []
    for para in p["body"].splitlines() or [""]:
        for ch in {c for c in para if ord(c) not in cmap and not c.isspace()}:
            lost.add(ch)
        para = "".join(c for c in para if ord(c) in cmap)
        cur, x, end = [], 0.0, 0.0                  # end: where the last visible letter's advance ends
        for w in re.findall(r"\s*\S+|\s+", para):
            vis = sum(adv(c) for c in w.rstrip())
            if p["boxWidth"] and cur and w.strip() and x + vis > p["boxWidth"]:
                lines.append((cur, end))
                cur, x, end, w = [], 0.0, 0.0, w.lstrip()
            for c in w:
                cur.append((cmap[ord(c)], x))
                x += adv(c)
                end = x if not c.isspace() else end
        lines.append((cur, end))
    return lines


def outlines(p: dict, ctx: Ctx) -> tuple[list[dict], float, float] | None:
    """(Lottie contours in the text's own px from its box's top-left, own width, own height); None: font not found."""
    fam = _catalog()
    if p["font"] not in fam:
        ctx.say(f'text not exported: the font "{p["font"]}" is not in the app (it has: {", ".join(sorted(fam))})')
        return None
    font = _font(fam[p["font"]])
    loc = _location(font, p, p["axes"])
    gs, upm = font.getGlyphSet(location=dict(loc)), font["head"].unitsPerEm
    k, hh = p["size"] / upm, font["hhea"]
    lost: set = set()
    lines = _lines(p, gs, font.getBestCmap(), k, lost)
    width = p["boxWidth"] or max((w for _, w in lines), default=0.0)
    lh = p["lineHeight"] * p["size"]
    lead = (lh - (hh.ascent - hh.descent) * k) / 2
    out = []
    for n, (glyphs, w) in enumerate(lines):
        x0 = {"left": 0.0, "center": (width - w) / 2, "right": width - w}[p["align"]]
        for name, x in glyphs:
            pen = _Pen(gs, k, x0 + x, n * lh + lead + hh.ascent * k)
            gs[name].draw(pen)
            out += pen.out
    if lost:
        ctx.say(f'letters the font has no glyph for are left out: {" ".join(sorted(lost))}')
    return out, width, lh * len(lines)


def _say_undone(node: dict, p: dict, ctx: Ctx, own: tuple, engine) -> None:
    for name, default in UNDONE.items():
        if p[name] != default:
            ctx.say(f'font feature "{name}" is not applied (the letters are the font\'s plain ones)')
    ctx.say("kerning pairs are not applied: letter spacing is the plain advance widths, so pairs like AV sit looser than on screen")
    if p["path"] or p["pathLayer"]:
        ctx.say("text on a path is drawn as a straight line")
    if p["letterDelay"]:
        ctx.say("per-letter animation (letter delay) is not exported; the text moves as one")
    if engine and abs(engine[0] - own[0]) > 1.5:
        ctx.say(f"text box: the engine's is {engine[0]:.0f} px wide, our layout's {own[0]:.0f} px; glyphs follow ours")
    if not engine:
        ctx.say("the engine is not built, so the text box (anchor, alignment) comes from our own layout, not the engine's")


def text_layer(node: dict, ctx: Ctx, ind: int) -> dict:
    """The Lottie shape layer for a text item (the layer's `anim` for position, colour, opacity … stays on it)."""
    held = frozen(node, HELD, ctx, "a Lottie glyph outline can't follow it")
    got = outlines(held, ctx)
    if got is None:
        return {}
    shapes, w, h = got
    try:
        engine = textsize.size(held)
    except Exception:                    # no engine built: the box is our own
        engine = None
    box = engine or (w, h)
    _say_undone(node, held, ctx, (w, h), engine)
    sized = {**node, "props": {**node["props"], "w": box[0], "h": box[1]}}
    layer = common(sized, ctx, 4, ind)
    fx = next((e for e in node.get("effects", []) if e["type"] == "gradient"), None)
    grad = gradient(fx, sized, ctx)
    fill = {**grad, "r": 1} if grad else {"ty": "fl", "nm": "fill", "o": _STILL(100), "r": 1,
                                         "c": build(node, ["color"], lambda q: rgb(q["color"]), ctx, "text colour")}
    glyphs = [{"ty": "sh", "nm": "glyph", "ks": _STILL(s)} for s in shapes]
    parts = [*glyphs]
    if held["stroke"]:
        parts.append({**_stroke(node, ctx, None, False), "lj": 2})   # listed before the fill = drawn on top of it
    layer["shapes"] = [group("text", [*parts, fill])]
    return layer
