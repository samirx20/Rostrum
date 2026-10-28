"""Typeset maths as path layers: `math_text(id, r"\\frac{a}{b}", x=, y=, size=, color=)` (guides/data-math-and-graphs.md).

LaTeX-style input is typeset by matplotlib's mathtext (its parser and layout, with its bundled STIX / DejaVu math fonts,
SIL OFL / Bitstream licences; matplotlib is already in the venv for Sound) and comes out as ordinary path layers in a
group: one path per glyph, one per fraction bar / root bar / rule. Each is addressable, so a term can be revealed,
coloured or moved like any path. Nothing here draws; the layers are plain `path` layers (field d, comp px).

Ids: `<id>_<n>_<what>`, n counting from 1 in reading order (left to right), what the symbol ("f", "sum", "pi", "2",
"bar" for a rule): `eq_3_equal`, `eq_9_sum`, `eq_10_bar`. `math_parts(tex, size)` lists them without making layers.
"""
from __future__ import annotations

import math
import unicodedata

MAX_CHARS = 600

_SLUG = {"=": "equal", "+": "plus", "-": "minus", "\u2212": "minus", "(": "lparen", ")": "rparen", "[": "lbracket", "]": "rbracket",
         "/": "slash", ",": "comma", ".": "dot", "<": "less", ">": "greater", "\u00d7": "times", "\u00b1": "plusminus",
         "|": "bar", ":": "colon", "!": "bang", "'": "prime", "\u2032": "prime", "\u221a": "root", "\u221e": "infty",
         "\u2211": "sum", "\u220f": "prod", "\u222b": "int", "\u2202": "partial", "\u2207": "nabla", "\u00b7": "cdot",
         "\u22c5": "cdot", "\u2264": "le", "\u2265": "ge", "\u2260": "ne", "\u2248": "approx", "\u2192": "to", "{": "lbrace", "}": "rbrace"}


def _slug(ch: str) -> str:
    if ch in _SLUG:
        return _SLUG[ch]
    if ch.isalnum() and ch.isascii():
        return ch
    try:
        name = unicodedata.name(ch).lower()
    except ValueError:
        return "sym"
    name = name.replace("greek small letter ", "").replace("greek capital letter ", "cap_").replace("n-ary ", "")
    return "".join(c if c.isalnum() else "_" for c in name).strip("_")[:16] or "sym"


def _cubic(cur, q, p):
    return ("C", cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]),
            p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]), p[0], p[1])


def _d(verts, codes, ox, oy, scale) -> str:
    """matplotlib path (y up, font units) -> SVG path data in px at (ox, oy) (y down)."""
    def pt(i):
        return ox + float(verts[i][0]) * scale, oy - float(verts[i][1]) * scale
    out, i, cur, start = [], 0, (0.0, 0.0), (0.0, 0.0)
    n = len(codes)
    while i < n:
        c = int(codes[i])
        if c == 1:                                   # MOVETO
            cur = start = pt(i)
            out.append(f"M{cur[0]:.2f} {cur[1]:.2f}")
            i += 1
        elif c == 2:                                 # LINETO
            cur = pt(i)
            out.append(f"L{cur[0]:.2f} {cur[1]:.2f}")
            i += 1
        elif c == 3:                                 # CURVE3: control, end (as the same curve in cubic form)
            seg = _cubic(cur, pt(i), pt(i + 1))
            cur = pt(i + 1)
            out.append("C" + " ".join(f"{v:.2f}" for v in seg[1:]))
            i += 2
        elif c == 4:                                 # CURVE4
            out.append("C" + " ".join(f"{pt(i + k)[j]:.2f}" for k in range(3) for j in range(2)))
            cur = pt(i + 2)
            i += 3
        elif c == 79:                                # CLOSEPOLY
            out.append("Z")
            cur = start
            i += 1
        else:
            i += 1
    return " ".join(out)


def math_parts(tex: str, size: float = 64, x: float = 0, y: float = 0) -> list[tuple[str, str]]:
    """[(what, d), …] in reading order: the symbols and rules of `tex`, as path data in px with the origin at the top-left
    of what is drawn at (x, y). A bad formula raises ValueError saying what the parser did not understand."""
    if not isinstance(tex, str) or not tex.strip():
        raise ValueError("math_text: give the formula as a string, e.g. r\"\frac{1}{2}\"")
    if len(tex) > MAX_CHARS:
        raise ValueError(f"math_text: {len(tex)} characters is too long (at most {MAX_CHARS}); typeset it in several pieces")
    if not size > 0:
        raise ValueError(f"math_text: size {size!r} must be above 0 (px)")
    import matplotlib
    from matplotlib.font_manager import FontProperties
    from matplotlib.ft2font import LoadFlags
    from matplotlib.mathtext import MathTextParser
    s = tex.strip()
    if not (s.startswith("$") and s.endswith("$") and len(s) > 1):
        s = f"${s}$"
    try:
        with matplotlib.rc_context({"mathtext.fontset": "stix"}):
            parsed = MathTextParser("path").parse(s, 72, FontProperties(size=size))
    except Exception as e:                       # matplotlib raises ValueError: the formula, a caret under the error, the reason
        lines = [ln.strip() for ln in str(e).splitlines() if ln.strip()]
        raise ValueError(f"math_text: can't typeset {tex!r}: {lines[-1] if lines else type(e).__name__}. "
                         r"Check braces and \commands (\frac{a}{b}, \sqrt{x}, \sum_{k=1}^{n}, \pi, x^2, x_i)") from None
    items = []                                   # (left, y_up_top, what, builder)
    for font, fsize, num, _gi, ox, oy in parsed.glyphs:
        font.set_size(100, 72)
        font.load_char(num, flags=LoadFlags.NO_HINTING)
        verts, codes = font.get_path()
        if len(codes) == 0:
            continue
        k = fsize / 100
        items.append((ox, oy + float(verts[:, 1].max()) * k, _slug(chr(num)), (verts, codes, ox, oy, k)))
    for rx, ry, w, h in parsed.rects:
        h = max(h, size * 0.04)                  # a rule always shows
        items.append((rx, ry + h, "bar", (rx, ry, w, h)))
    if not items:
        raise ValueError(f"math_text: {tex!r} typesets to nothing visible")
    left, top = min(i[0] for i in items), max(i[1] for i in items)
    out = []
    for _l, _t, what, a in sorted(items, key=lambda t: (t[0], -t[1])):
        if what == "bar":
            bx0, by0, w, h = a
            bx, by = x + bx0 - left, y + top - by0
            d = f"M{bx:.2f} {by:.2f} L{bx + w:.2f} {by:.2f} L{bx + w:.2f} {by - h:.2f} L{bx:.2f} {by - h:.2f} Z"
        else:
            verts, codes, ox, oy, k = a
            d = _d(verts, codes, x + ox - left, y + top - oy, k)
        out.append((what, d))
    return out


def _typeset_class():
    from .script import Item

    class Typeset(Item):
        """The group `math_text` made. `.parts`: its path layers in reading order; `.find("sum")`: those of one symbol
        ("x", "2", "equal", "bar", "pi" …); `.span(a, b)`: parts a to b (1-based, as in the ids), a term."""
        def __init__(self, build, node, made):
            super().__init__(build, node)
            object.__setattr__(self, "_made", made)
            object.__setattr__(self, "parts", [p for _w, p in made])

        def find(self, what: str) -> list:
            return [p for w, p in self._made if w == what]

        def span(self, first: int, last: int) -> list:
            if not 1 <= first <= last <= len(self.parts):
                raise ValueError(f"{self.id}.span({first}, {last}): the formula has parts 1 to {len(self.parts)}")
            return self.parts[first - 1:last]
    return Typeset


def for_script(layer) -> dict:
    """`math_text(id, tex, x=0, y=0, size=64, color="#ffffff", **path_fields)` for scripts: a group `id` holding one path
    layer per symbol and rule (ids `<id>_<n>_<what>`), the formula's top-left at (x, y) in comp px, `size` the font size in
    px. Gives the group; `.parts` / `.find(symbol)` / `.span(first, last)` give its path layers (or address one by its id). Fields beyond these (opacity, rotation, scale) go to the group; others (stroke=,
    strokeColor=, strokeWidth=, fill="none" …) to every path."""
    from . import pathdata
    path = pathdata.for_script(layer)["path"]
    Typeset = _typeset_class()

    def math_text(id=None, tex=None, x=0, y=0, size=64, color="#ffffff", **fields):
        if tex is None:
            raise ValueError('math_text(id, tex, x=, y=, size=, color=): give the formula, e.g. math_text("eq", r"\\frac{1}{2}")')
        parts = math_parts(tex, size)
        w = h = 0.0
        for _what, d in parts:
            x1, y1 = pathdata.bounds(pathdata.commands(d))[2:]
            w, h = max(w, x1), max(h, y1)
        group = layer("group", id, w=round(w, 2), h=round(h, 2), x=x + w / 2, y=y + h / 2, **{k: fields.pop(k) for k in ("opacity", "rotation", "scale", "name") if k in fields})
        base = group.id
        made = []
        with group:
            for n, (what, d) in enumerate(parts, 1):
                made.append((what, path(f"{base}_{n}_{what}", d=d, **{"fill": color, "stroke": False, **fields})))
        return Typeset(group._b, group.node, made)
    return {"math_text": math_text}


def bounds(parts) -> tuple[float, float]:
    """(w, h) of the parts' box in px."""
    from . import pathdata
    w = h = 0.0
    for _what, d in parts:
        x1, y1 = pathdata.bounds(pathdata.commands(d))[2:]
        w, h = max(w, x1), max(h, y1)
    return round(w, 2), round(h, 2)
