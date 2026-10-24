"""Text layers → Lottie shape layers made of glyph outlines (fontTools, MIT), grouped per text layer.

Why outlines and not a Lottie text layer (ty 5): a ty 5 layer needs the font on the viewer's machine (or a font asset),
and lottie-web, Skottie and rlottie each lay it out differently; outlines are plain bezier shapes that every player
draws the same. The layer keeps its transform, opacity, blend, masks, colour keys and gradient like any other layer.

Layout: the engine only measures a text's box (textsize.py); the glyph positions are not reachable from Python. So this
module lays the glyphs out itself, shaped by HarfBuzz (uharfbuzz, Apache-2.0, the shaper the engine's text uses) at the
weight / width / optical size the text asks for: kerning, ligatures, small caps, figure styles and `features` applied;
`tracking`, `lineHeight`, line breaks, wrapping at `boxWidth`, `align`; baseline by the engine's line-box rule (lottie_glyphs.baseline: ascent / descent
rounded to px, half-leading floored, line top rounded). When
the engine is built, its box is used for the layer's box and the report says how far our line lengths are from it.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from .. import settings, textsize
from .lottie_glyphs import baseline, lines as _lines, metrics, shaper
from .lottie_layer import common
from .lottie_props import Ctx, build, fill_opacity, frozen, rgb
from .lottie_shapes import _STILL, _stroke, gradient, group

HELD = ["body", "font", "size", "weight", "stretch", "tracking", "lineHeight", "align", "boxWidth", "slant", "grade", "stroke"]


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


def _catalog() -> dict[str, Path]:
    """Family name → its upright font file, from the engine's one list (fontlist.py)."""
    from ..fontlist import families
    return {f["family"]: Path(f["files"][0]) for f in families()}


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


def outlines(p: dict, ctx: Ctx) -> tuple[list[dict], float, float] | None:
    """(Lottie contours in the text's own px from its box's top-left, own width, own height); None: font not found."""
    fam = _catalog()
    if p["font"] not in fam:
        ctx.say(f'text not exported: the font "{p["font"]}" is not in the app or on this computer')
        return None
    font = _font(fam[p["font"]])
    loc = _location(font, p, p["axes"])
    gs, upm = font.getGlyphSet(location=dict(loc)), font["head"].unitsPerEm
    k, (asc, desc) = p["size"] / upm, metrics(font, p["size"])
    lost: set = set()
    hb_font = shaper(fam[p["font"]], loc)
    lines = _lines(p, hb_font, font.getBestCmap(), k, lost)
    width = p["boxWidth"] or max((w for _, w in lines), default=0.0)
    lh = p["lineHeight"] * p["size"]
    out = []
    for n, (glyphs, w) in enumerate(lines):
        x0 = {"left": 0.0, "center": (width - w) / 2, "right": width - w}[p["align"]]
        for gid, x in glyphs:
            pen = _Pen(gs, k, x0 + x, baseline(n, lh, asc, desc))
            gs[font.getGlyphName(gid)].draw(pen)
            out += pen.out
    if lost:
        ctx.say(f'letters the font has no glyph for are left out: {" ".join(sorted(lost))}')
    return out, width, lh * len(lines)


def _say_undone(node: dict, p: dict, ctx: Ctx, own: tuple, engine) -> None:
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
    fill = {**grad, "r": 1} if grad else {"ty": "fl", "nm": "fill", "o": fill_opacity(node, ctx), "r": 1,
                                         "c": build(node, ["color"], lambda q: rgb(q["color"]), ctx, "text colour")}
    glyphs = [{"ty": "sh", "nm": "glyph", "ks": _STILL(s)} for s in shapes]
    parts = [*glyphs]
    if held["stroke"]:
        parts.append({**_stroke(node, ctx, None, False), "lj": 2})   # listed before the fill = drawn on top of it
    layer["shapes"] = [group("text", [*parts, fill])]
    return layer
