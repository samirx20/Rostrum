"""Small readers over pdfium's raw page-object calls (pypdfium2, BSD-3 / Apache-2.0; pdfium BSD). Matrices are
(a, b, c, d, e, f): x' = a·x + c·y + e, y' = b·x + d·y + f. Never MuPDF (AGPL)."""
from __future__ import annotations

import ctypes as C
import math

import pypdfium2.raw as R

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
CAP = {0: "butt", 1: "round", 2: "square"}
JOIN = {0: "miter", 1: "round", 2: "bevel"}


def matrix(obj) -> tuple:
    m = R.FS_MATRIX()
    if not R.FPDFPageObj_GetMatrix(obj, m):
        raise ValueError("pdfium could not read an object's matrix")
    return (m.a, m.b, m.c, m.d, m.e, m.f)


def compose(inner, outer) -> tuple:
    """`inner` first, then `outer`."""
    a, b, c, d, e, f = inner
    A, B, Cc, D, E, F = outer
    return (a * A + b * Cc, a * B + b * D, c * A + d * Cc, c * B + d * D, e * A + f * Cc + E, e * B + f * D + F)


def apply(m, x, y) -> tuple:
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def scale_of(m) -> float:
    return math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))


def _rgba(fn, obj) -> str:
    r, g, b, a = (C.c_uint() for _ in range(4))
    if not fn(obj, r, g, b, a):
        raise ValueError("pdfium could not read an object's colour")
    return "#%02x%02x%02x%02x" % (r.value, g.value, b.value, a.value)


def fill_colour(obj) -> str:
    return _rgba(R.FPDFPageObj_GetFillColor, obj)


def stroke_colour(obj) -> str:
    return _rgba(R.FPDFPageObj_GetStrokeColor, obj)


def stroke_width(obj) -> float:
    w = C.c_float()
    R.FPDFPageObj_GetStrokeWidth(obj, w)
    return w.value


def draw_mode(obj) -> tuple[int, bool]:
    """(fill mode: 0 none, 1 even-odd, 2 nonzero; stroked?)."""
    fill, stroke = C.c_int(), C.c_int()
    if not R.FPDFPath_GetDrawMode(obj, fill, stroke):
        raise ValueError("pdfium could not read a path's draw mode")
    return fill.value, bool(stroke.value)


def segments(obj) -> list[tuple]:
    """Path segments in the object's own space: ("M", x, y) / ("L", x, y) / ("C", x1, y1, x2, y2, x, y) / ("Z",)."""
    n, out, bez = R.FPDFPath_CountSegments(obj), [], []
    for i in range(n):
        seg = R.FPDFPath_GetPathSegment(obj, i)
        x, y = C.c_float(), C.c_float()
        R.FPDFPathSegment_GetPoint(seg, x, y)
        kind = R.FPDFPathSegment_GetType(seg)
        if kind == R.FPDF_SEGMENT_MOVETO:
            out.append(("M", x.value, y.value))
        elif kind == R.FPDF_SEGMENT_LINETO:
            out.append(("L", x.value, y.value))
        elif kind == R.FPDF_SEGMENT_BEZIERTO:
            bez += [x.value, y.value]
            if len(bez) == 6:
                out.append(("C", *bez))
                bez = []
        else:
            raise ValueError(f"unknown path segment type {kind}")
        if R.FPDFPathSegment_GetClose(seg):
            out.append(("Z",))
    if bez:
        raise ValueError("a path ends in the middle of a curve")
    return out


def has_dash(obj) -> bool:
    return R.FPDFPageObj_GetDashCount(obj) > 0
