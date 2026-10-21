"""Text shaped into lines of glyphs for the Lottie export (lottie_text.py draws them). HarfBuzz (uharfbuzz,
Apache-2.0) shapes each paragraph, so kerning, ligatures and the text's OpenType settings come out as the engine's text
does; lines break at new lines and wrap at word ends past `boxWidth`."""
from __future__ import annotations

import math
import re
from pathlib import Path

import uharfbuzz as hb


def shaper(path: Path, location: tuple):
    """A HarfBuzz font for a font file at a variable-axis location ((tag, value), …)."""
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    font.set_variations(dict(location))
    return font


def metrics(font, size: float) -> tuple[float, float]:
    """(ascent, descent) in px as the engine's text shaper reads them: OS/2 typo metrics when the font sets
    USE_TYPO_METRICS (fsSelection bit 7) and has them, else hhea."""
    upm, os2, hh = font["head"].unitsPerEm, font["OS/2"] if "OS/2" in font else None, font["hhea"]
    if os2 is not None and os2.fsSelection & 128 and (os2.sTypoAscender or os2.sTypoDescender):
        return os2.sTypoAscender * size / upm, -os2.sTypoDescender * size / upm
    return hh.ascent * size / upm, -hh.descent * size / upm


def baseline(n: int, line_height: float, ascent: float, descent: float) -> float:
    """Distance from the text box's top to line n's baseline, by the engine's rule (parley, quantized, as CSS in
    Chromium): ascent and descent each round to whole px, the half-leading above the baseline is floored, and the
    line's top (n lines of `line_height` down) rounds to a whole px."""
    near = lambda x: math.floor(x + 0.5)            # Rust's round (half up), not Python's half-to-even
    a, d = near(ascent), near(descent)
    return near(n * line_height) + a + math.floor((line_height - (a + d)) / 2)


def _features(p: dict) -> dict:
    """The text's type settings as OpenType features for the shaper (the same tags the engine's CSS sets)."""
    f = {} if p["ligatures"] else {"liga": False, "clig": False}
    if p["smallCaps"]:
        f["smcp"] = True
    spacing, _, kind = p["figures"].partition(" ")
    f.update({"tabular": {"tnum": True}, "proportional": {"pnum": True}}.get(spacing, {}))
    f.update({"lining": {"lnum": True}, "old-style": {"onum": True}}.get(kind, {}))
    for tag, val in re.findall(r"(\w{4})(?:=(\d+))?", p["features"]):
        f[tag] = int(val) if val else True
    return f


def _shaped(hb_font, text: str, features: dict) -> list[tuple[int, float, int]]:
    """[(glyph id, advance in font units, character index)]: HarfBuzz shaping, so kerning and the font's default
    features (ligatures, contextual forms) are applied as the engine's text shaper applies them."""
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, features)
    return [(i.codepoint, p.x_advance, i.cluster) for i, p in zip(buf.glyph_infos, buf.glyph_positions)]


def lines(p: dict, hb_font, cmap: dict, k: float, lost: set) -> list[tuple[list, float]]:
    """[(glyph ids with their pen x, line width)] per line: breaks at a new line, wrapped at boxWidth when it is set."""
    track = p["tracking"] * p["size"]
    lines = []
    for para in p["body"].splitlines() or [""]:
        for ch in {c for c in para if ord(c) not in cmap and not c.isspace()}:
            lost.add(ch)
        para = "".join(c for c in para if ord(c) in cmap)
        glyphs = _shaped(hb_font, para, _features(p))
        cur, x, end = [], 0.0, 0.0                  # end: where the last visible letter's advance ends
        for m in re.finditer(r"\s*\S+|\s+", para):
            run = [g for g in glyphs if m.start() <= g[2] < m.end()]
            vis_end = m.start() + len(m.group().rstrip())
            vis = sum(a * k + track for _, a, c in run if c < vis_end)
            if p["boxWidth"] and cur and m.group().strip() and x + vis > p["boxWidth"]:
                lines.append((cur, end))
                cur, x, end = [], 0.0, 0.0
                run = [g for g in run if not para[g[2]].isspace()]
            for gid, a, c in run:
                cur.append((gid, x))
                x += a * k + track
                end = x if not para[c].isspace() else end
        lines.append((cur, end))
    return lines
