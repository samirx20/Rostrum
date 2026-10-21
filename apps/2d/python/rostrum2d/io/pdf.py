"""PDF page → import tree (pypdfium2: Apache-2.0 / BSD-3; pdfium: BSD). Path objects → path layers, text objects →
text layers, image objects → image layers, form XObjects → groups. PDF is y-up; the tree is y-down (page height flips).
1 point = 1 px unless `scale` says otherwise. Shadings and clip paths can't be carried over (reported).
"""
from __future__ import annotations

import ctypes
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as R
from pypdfium2._helpers.pageobjects import PdfObject

from .. import pathdata as PD
from . import pdf_raw as P


def pdf_tree(path, page: int = 0, scale: float = 1.0) -> dict:
    """Read page `page` (0-based) of a PDF → the import tree. Only fonts in `fonts` of tree.import_into are checked there."""
    path = Path(path)
    pdf = pdfium.PdfDocument(str(path))
    try:
        pg = pdf[page]
        w, h = pg.get_size()
        ctx = {"pdf": pdf, "page": pg, "text": pg.get_textpage(), "h": h, "s": scale, "report": [], "n": 0}
        layers = _walk(ctx, lambda: _objects(ctx, pg), P.IDENTITY)
        if not layers:
            raise ValueError(f"{path.name} page {page + 1} has nothing to import")
        return {"name": path.name, "width": w * scale, "height": h * scale, "layers": layers, "report": ctx["report"]}
    finally:
        pdf.close()


def _objects(ctx, parent, form=None, level=0):
    count, get = ((R.FPDFFormObj_CountObjects, R.FPDFFormObj_GetObject) if form is not None
                  else (R.FPDFPage_CountObjects, R.FPDFPage_GetObject))
    holder = form.raw if form is not None else parent.raw
    for i in range(count(holder)):
        yield PdfObject(get(holder, i), page=ctx["page"], pdf=ctx["pdf"], container=form, level=level,
                        textpage=ctx["text"])


def _walk(ctx, objects, outer) -> list[dict]:
    out = []
    for obj in objects():
        m = P.compose(P.matrix(obj.raw), outer)
        t, node = obj.type, None
        if t == R.FPDF_PAGEOBJ_FORM:
            kids = _walk(ctx, lambda o=obj: _objects(ctx, None, o, 1), m)
            if kids:
                out.append({"type": "group", "name": _name(ctx, "Group"), "props": {}, "layers": kids})
        elif t == R.FPDF_PAGEOBJ_PATH:
            node = _path(ctx, obj, m)
        elif t == R.FPDF_PAGEOBJ_TEXT:
            node = _text(ctx, obj, m, outer)
        elif t == R.FPDF_PAGEOBJ_IMAGE:
            node = _image(ctx, obj, m)
        else:
            ctx["report"].append("a shading or unknown object was left out (not carried over)")
            continue
        if node:
            out.append(node)
    return out


def _name(ctx, base: str) -> str:
    ctx["n"] += 1
    return f"{base} {ctx['n']}"


def _flip(ctx, m):
    s, h = ctx["s"], ctx["h"]
    return lambda x, y: tuple(v * s for v in (lambda p: (p[0], h - p[1]))(P.apply(m, x, y)))


def _path(ctx, obj, m) -> dict | None:
    segs = P.segments(obj)
    if not segs:
        return None
    fill_mode, stroked = P.draw_mode(obj)
    cmds = PD.transformed(segs, _flip(ctx, m))
    x0, y0, x1, y1 = PD.bounds(cmds)
    props = {"d": PD.write(cmds), "filled": fill_mode != 0}
    if fill_mode:
        props.update(fill=P.fill_colour(obj), fillRule="evenodd" if fill_mode == 1 else "nonzero")
    if stroked:
        props.update(stroke=True, strokeColor=P.stroke_colour(obj), cap=P.CAP[R.FPDFPageObj_GetLineCap(obj)],
                     join=P.JOIN[R.FPDFPageObj_GetLineJoin(obj)],
                     strokeWidth=P.stroke_width(obj) * P.scale_of(m) * ctx["s"])
    name = _name(ctx, "Path")
    if P.has_dash(obj):
        ctx["report"].append(f"'{name}': dashes were left out (drawn solid)")
    return {"type": "path", "name": name, "box": [x0, y0, max(x1 - x0, 1.0), max(y1 - y0, 1.0)], "props": props}


def _text(ctx, obj, m, outer) -> dict | None:
    body = obj.extract()
    if not body.strip():
        return None
    font = obj.get_font()
    family = font.get_base_name().split("+")[-1]
    size = obj.get_font_size() * P.scale_of(m) * ctx["s"]
    l, b, r, t = (ctypes.c_float() for _ in range(4))
    R.FPDFPageObj_GetBounds(obj.raw, l, b, r, t)
    pts = [_flip(ctx, outer)(x, y) for x in (l.value, r.value) for y in (b.value, t.value)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"type": "text", "name": body.strip()[:30], "box": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)],
            "props": {"body": body.replace("\r\n", "\n"), "size": max(size, 1.0), "color": P.fill_colour(obj.raw),
                      "align": "left", "font": family, "weight": float(font.get_weight() or 400)}}


def _image(ctx, obj, m) -> dict | None:
    raw = R.FPDFImageObj_GetRenderedBitmap(ctx["pdf"].raw, ctx["page"].raw, obj.raw)
    if not raw:
        raise ValueError("pdfium could not render an image object")
    img = pdfium.PdfBitmap.from_raw(raw).to_pil().convert("RGBA")
    f = _flip(ctx, m)
    pts = [f(x, y) for x in (0, 1) for y in (0, 1)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"type": "image", "name": _name(ctx, "Image"), "image": img, "props": {"fit": "stretch"},
            "box": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]}
