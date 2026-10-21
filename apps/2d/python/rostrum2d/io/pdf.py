"""PDF page → import tree (pypdfium2: Apache-2.0 / BSD-3; pdfium: BSD). Path objects → path layers, text objects →
text layers, image objects → image layers, form XObjects → groups. PDF is y-up; the tree is y-down (page height flips).
1 point = 1 px unless `scale` says otherwise. pdfium hides shadings and clip paths, so pdf_content.py reads them from the
content stream: shadings (axial / radial) → a gradient effect (pdf_shading.py), clip paths → a track matte (pdf_clip.py).
One page → `pdf_tree`; every page → `pdf_pages` (importing.py makes one composition per page).
"""
from __future__ import annotations

import ctypes
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as R
from pypdf import PdfReader
from pypdfium2._helpers.pageobjects import PdfObject

from .. import pathdata as PD
from . import pdf_clip as K
from . import pdf_content as C
from . import pdf_font as FONT
from . import pdf_raw as P
from .pdf_shading import gradient

KIND_TYPE = {"path": R.FPDF_PAGEOBJ_PATH, "text": R.FPDF_PAGEOBJ_TEXT, "image": R.FPDF_PAGEOBJ_IMAGE,
             "form": R.FPDF_PAGEOBJ_FORM, "shading": R.FPDF_PAGEOBJ_SHADING}


def pdf_tree(path, page: int = 0, scale: float = 1.0) -> dict:
    """Read page `page` (0-based) of a PDF → the import tree. Only fonts in `fonts` of tree.import_into are checked there."""
    return _trees(Path(path), [page], scale, strict=True)[0]


def pdf_pages(path, scale: float = 1.0) -> list[dict]:
    """Every page → one import tree each, named "Page N" (or the page's own label); an empty page keeps its tree, with a report line."""
    pdf = pdfium.PdfDocument(str(path))
    n = len(pdf)
    pdf.close()
    return _trees(Path(path), list(range(n)), scale, strict=False)


def _trees(path: Path, pages: list[int], scale: float, strict: bool) -> list[dict]:
    pdf, reader, out = pdfium.PdfDocument(str(path)), PdfReader(str(path)), []
    try:
        labels = reader.page_labels
        for i in pages:
            pg = pdf[i]
            w, h = pg.get_size()
            ctx = {"pdf": pdf, "page": pg, "text": pg.get_textpage(), "h": h, "s": scale, "report": [], "n": 0, "reader": reader}
            events, notes = C.page_events(reader, i, (0.0, 0.0, w, h))
            ctx["report"] += notes
            layers = _walk(ctx, lambda: _objects(ctx, pg), P.IDENTITY, events)
            label = labels[i] if i < len(labels) else str(i + 1)
            name = "Page %d" % (i + 1) if label == str(i + 1) else label
            if not layers:
                if strict:
                    raise ValueError(f"{path.name} page {i + 1} has nothing to import")
                ctx["report"].append("an empty page: nothing to import")
            out.append({"name": path.name, "comp": name, "width": w * scale, "height": h * scale, "layers": layers,
                        "report": [f"{name}: {r}" for r in ctx["report"]] if len(pages) > 1 else ctx["report"]})
        return out
    finally:
        pdf.close()


def _objects(ctx, parent, form=None, level=0):
    count, get = ((R.FPDFFormObj_CountObjects, R.FPDFFormObj_GetObject) if form is not None
                  else (R.FPDFPage_CountObjects, R.FPDFPage_GetObject))
    holder = form.raw if form is not None else parent.raw
    for i in range(count(holder)):
        yield PdfObject(get(holder, i), page=ctx["page"], pdf=ctx["pdf"], container=form, level=level,
                        textpage=ctx["text"])


def _say(ctx, line: str):
    if line not in ctx["report"]:
        ctx["report"].append(line)


def _pair(ctx, objs, events) -> dict:
    """The events of each kind in painting order; a kind whose count differs from pdfium's can't be lined up, and is said."""
    seq = {}
    for kind, t in KIND_TYPE.items():
        mine, theirs = [e for e in events if e["kind"] == kind], sum(1 for o in objs if o.type == t)
        if len(mine) == theirs:
            seq[t] = iter(mine)
        elif kind != "text" or any(e["clips"] for e in mine):
            _say(ctx, f"{kind} objects could not be lined up with the file's drawing commands ({theirs} found, {len(mine)} read): "
                      "their gradients and clip paths are not carried over")
    return seq


def _walk(ctx, objects, outer, events) -> list[dict]:
    objs = list(objects())
    seq, items, to_px = _pair(ctx, objs, events), [], _flip(ctx, outer)
    for obj in objs:
        m = outer if obj.type == R.FPDF_PAGEOBJ_SHADING else P.compose(P.matrix(obj.raw), outer)   # a shading has no matrix of its own
        t, node, ev = obj.type, None, next(seq.get(obj.type, iter(())), None)
        if t == R.FPDF_PAGEOBJ_FORM:
            sub, notes = C.form_events(ctx["reader"], ev["xobj"], ev["resources"]) if ev else ([], [])
            for line in notes:
                _say(ctx, line)
            kids = _walk(ctx, lambda o=obj: _objects(ctx, None, o, 1), m, sub)
            if kids:
                node = {"type": "group", "name": _name(ctx, "Group"), "props": {}, "layers": kids}
        elif t == R.FPDF_PAGEOBJ_PATH:
            node = _path(ctx, obj, m, ev, outer)
        elif t == R.FPDF_PAGEOBJ_TEXT:
            node = _text(ctx, obj, m, outer)
        elif t == R.FPDF_PAGEOBJ_IMAGE:
            node = _image(ctx, obj, m)
        elif t == R.FPDF_PAGEOBJ_SHADING and ev:
            node = _shading(ctx, ev, outer)
        else:
            _say(ctx, "an object pdfium could not name was left out (not carried over)")
        if node:
            margin = node["props"].get("strokeWidth", 0.0) / 2 if node["props"].get("stroke") else 0.0
            items.append((node, K.needed(K.px_clips(ev["clips"], to_px), K.box_of(node), margin) if ev else ()))
    return K.wrap(items, lambda base: _name(ctx, base))


def _name(ctx, base: str) -> str:
    ctx["n"] += 1
    return f"{base} {ctx['n']}"


def _flip(ctx, m):
    s, h = ctx["s"], ctx["h"]
    return lambda x, y: tuple(v * s for v in (lambda p: (p[0], h - p[1]))(P.apply(m, x, y)))


def _path(ctx, obj, m, ev, outer) -> dict | None:
    segs = P.segments(obj)
    if not segs:
        return None
    fill_mode, stroked = P.draw_mode(obj)
    cmds = PD.transformed(segs, _flip(ctx, m))
    x0, y0, x1, y1 = PD.bounds(cmds)
    props = {"d": PD.write(cmds), "filled": fill_mode != 0}
    shade = ev and ev["shade"]
    if fill_mode:
        props.update(fill="#808080" if shade else P.fill_colour(obj), fillRule="evenodd" if fill_mode == 1 else "nonzero")
    if stroked:
        props.update(stroke=True, strokeColor=P.stroke_colour(obj), cap=P.CAP[R.FPDFPageObj_GetLineCap(obj)],
                     join=P.JOIN[R.FPDFPageObj_GetLineJoin(obj)],
                     strokeWidth=P.stroke_width(obj) * P.scale_of(m) * ctx["s"])
    name, box = _name(ctx, "Path"), [x0, y0, max(x1 - x0, 1.0), max(y1 - y0, 1.0)]
    node = {"type": "path", "name": name, "box": box, "props": props}
    if P.has_dash(obj):
        _say(ctx, f"'{name}': dashes were left out (drawn solid)")
    if ev and ev["stroke_pattern"]:
        _say(ctx, f"'{name}': an outline painted with a gradient or pattern is drawn in one flat colour")
    if ev and ev["tiling"]:
        _say(ctx, f"'{name}': a tiling pattern fill is drawn as a flat grey")
    if shade:
        g = gradient(shade["shading"], _flip(ctx, P.compose(shade["matrix"], outer)), box, name, ctx["report"])
        if g:
            node["effects"] = [{"type": "gradient", "props": g}]
    return node


def _shading(ctx, ev, outer) -> dict | None:
    """An `sh` shading paints everything inside the clip: a rectangle of that area with the gradient on it."""
    to_px, sh = _flip(ctx, outer), ev["shade"]
    lx0, ly0, lx1, ly1 = ev["limit"]
    corners = [to_px(x, y) for x in (lx0, lx1) for y in (ly0, ly1)]
    cb = K.bounds(K.px_clips(ev["clips"], to_px))
    x0, y0 = max(min(c[0] for c in corners), cb[0] if cb else -1e9), max(min(c[1] for c in corners), cb[1] if cb else -1e9)
    x1, y1 = min(max(c[0] for c in corners), cb[2] if cb else 1e9), min(max(c[1] for c in corners), cb[3] if cb else 1e9)
    if x1 - x0 < 0.5 or y1 - y0 < 0.5:
        return None
    name, box = _name(ctx, "Shading"), [x0, y0, x1 - x0, y1 - y0]
    g = gradient(sh["shading"], _flip(ctx, P.compose(sh["matrix"], outer)), box, name, ctx["report"])
    if not g:
        return None
    d = PD.write([("M", x0, y0), ("L", x1, y0), ("L", x1, y1), ("L", x0, y1), ("Z",)])
    return {"type": "path", "name": name, "box": box, "props": {"d": d, "filled": True, "fill": "#808080"},
            "effects": [{"type": "gradient", "props": g}]}


def _text(ctx, obj, m, outer) -> dict | None:
    body = obj.extract()
    if not body.strip():
        return None
    family, weight, slant = FONT.of_text_object(obj)
    size = obj.get_font_size() * P.scale_of(m) * ctx["s"]
    l, b, r, t = (ctypes.c_float() for _ in range(4))
    R.FPDFPageObj_GetBounds(obj.raw, l, b, r, t)
    pts = [_flip(ctx, outer)(x, y) for x in (l.value, r.value) for y in (b.value, t.value)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"type": "text", "name": body.strip()[:30], "box": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)],
            "props": {"body": body.replace("\r\n", "\n"), "size": max(size, 1.0), "color": P.fill_colour(obj.raw),
                      "align": "left", "font": family, "weight": weight, **({"slant": slant} if slant else {})}}


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
