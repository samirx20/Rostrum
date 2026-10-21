"""Words as outlines: HarfBuzz shapes each line (kerning, ligatures, the font's own spacing), the glyphs are drawn at their
pen positions into one pathops Path, overlaps are merged, and the result is placed centred on the item origin.

Placement: a line block is as wide as its widest line; `align` puts that block's left edge, middle or right edge on
x = 0, and each line sits left / middle / right inside it. Vertically the block runs from the first line's capital
height down to the last baseline (so one line of caps is centred on y = 0 whatever letters it holds, and editing the
words never makes the text jump). Tracking and spacing come from the font's units, scaled by `size` (the em, in metres).
"""
from __future__ import annotations

import os
from pathlib import Path

import pathops
import uharfbuzz as hb
from fontTools.pens.transformPen import TransformPen

from . import outline as O

_FONTS = Path(os.environ.get("ROSTRUM_FONTS") or Path(__file__).resolve().parents[3] / "2d" / "engine" / "fonts")
_FACES: dict = {}


def shared_fonts() -> dict[str, Path]:
    """{name: file} of the fonts that ship with Rostrum (Inter, Recursive, RobotoFlex …)."""
    found = {}
    for f in sorted(_FONTS.glob("*")) if _FONTS.is_dir() else []:
        if f.suffix.lower() in (".ttf", ".otf"):
            found[f.stem.replace("Variable", "").replace("-Regular", "")] = f
    return found


def font_file(font: str) -> Path:
    shared = shared_fonts()
    if font in shared:
        return shared[font]
    low = {k.lower(): v for k, v in shared.items()}
    if font.lower() in low:
        return low[font.lower()]
    if font and Path(font).is_absolute() and Path(font).suffix.lower() in (".ttf", ".otf"):
        if Path(font).is_file():
            return Path(font)
        raise ValueError(f'font file "{font}" was not found')
    raise ValueError(f'unknown font "{font}"; use one of {", ".join(shared) or "(none found)"}, or the absolute path '
                     "of a .ttf / .otf file")


def _face(file: Path):
    key = (str(file), O.stamp(str(file)))
    if key not in _FACES:
        _FACES[key] = hb.Face(hb.Blob.from_file_path(str(file)))
    return _FACES[key]


def _weight_axis(face):
    return next((a for a in face.axis_infos if a.tag == "wght"), None)


def _line(font, text: str, track: float):
    """([(glyph, x, y)], width) of one line in font units: pen positions after shaping, tracking between letters."""
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    x, out = 0.0, []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        out.append((info.codepoint, x + pos.x_offset, pos.y_offset))
        x += pos.x_advance + track
    return out, max(0.0, x - track) if out else 0.0


def _cap_height(font, upem: int) -> float:
    gid = font.get_nominal_glyph(ord("H"))
    if gid is None:
        return 0.7 * upem
    p = pathops.Path()
    font.draw_glyph_with_pen(gid, p.getPen())
    return max(p.bounds[3], -p.bounds[1]) if p.bounds[3] != p.bounds[1] else 0.7 * upem


def text_outline(item: dict) -> list[dict]:
    text, font_name, size = item["text"], item["font"], float(item["size"])
    if not text.strip():
        raise ValueError(f'{item["id"]}: the text is empty; give it some words')
    if size <= 0:
        raise ValueError(f'{item["id"]}: size must be above 0 (metres, the height of the em)')
    file = font_file(font_name)
    key = ("text", text, str(file), O.stamp(str(file)), item["weight"], size, item["tracking"], item["lineHeight"], item["align"])
    return O.cached(key, lambda: _build(item, file, text, size))


def _build(item: dict, file: Path, text: str, size: float) -> list[dict]:
    face = _face(file)
    font, upem = hb.Font(face), face.upem
    axis = _weight_axis(face)
    if axis is not None:
        if not axis.min_value <= item["weight"] <= axis.max_value:
            raise ValueError(f'{item["id"]}: weight {item["weight"]:g} is outside this font\'s range '
                             f"{axis.min_value:g}–{axis.max_value:g}")
        font.set_variations({"wght": item["weight"]})
    elif item["weight"] != 400:
        raise ValueError(f'{item["id"]}: {file.name} has no weight axis; leave weight at 400, or pick a variable font '
                         f"({', '.join(shared_fonts())})")
    missing = sorted({c for c in text if not c.isspace() and font.get_nominal_glyph(ord(c)) is None})
    if missing:
        raise ValueError(f'{item["id"]}: {file.name} has no letters for {" ".join(missing)}; pick another font')
    track, step = item["tracking"] / 1000 * upem, item["lineHeight"] * upem
    lines = [_line(font, t, track) for t in text.split("\n")]
    block = max(w for _, w in lines)
    align = item["align"]
    path = pathops.Path()
    for n, (glyphs, width) in enumerate(lines):
        dx = {"left": 0.0, "center": (block - width) / 2, "right": block - width}[align]
        for gid, gx, gy in glyphs:
            font.draw_glyph_with_pen(gid, TransformPen(path.getPen(), (1, 0, 0, 1, gx + dx, gy - n * step)))
    path.simplify(fix_winding=True, keep_starting_points=False)
    scale = size / upem
    top, bottom = _cap_height(font, upem), -(len(lines) - 1) * step
    cx = {"left": 0.0, "center": block / 2, "right": block}[align]
    contours = O.contours_of(path, max(O.MIN_TOLERANCE, 0.002 * size) / scale)
    if not contours:
        raise ValueError(f'{item["id"]}: the text has no visible letters')
    return O.nest(O.place(contours, scale, (cx, (top + bottom) / 2), False))
