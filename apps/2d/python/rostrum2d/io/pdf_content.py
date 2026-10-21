"""What pdfium's page-object API hides, read from the content stream with pypdf (BSD-3): shadings (`sh` and shading-pattern
fills) and the clip paths in force on every object. One pass in painting order → one event per paint operation, in the
same order pdfium lists its objects, so pdf.py pairs them kind by kind. Coordinates are the container's own (the page, or
a form's own space), y-up; pdf.py applies the outer matrix and the flip. Never MuPDF."""
from __future__ import annotations

from pypdf.generic import ContentStream

from . import pdf_raw as P

FILL = {b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
STROKE = {b"S", b"s", b"B", b"B*", b"b", b"b*"}
SHOW = {b"Tj", b"TJ", b"'", b'"'}
TRANSPARENCY = "transparency (soft masks, blend modes) is not carried over"


def page_events(reader, index: int, limit) -> tuple[list[dict], list[str]]:
    page = reader.pages[index]
    return _run(ContentStream(page.get_contents(), reader), page.get("/Resources"), reader, limit, P.IDENTITY)


def form_events(reader, xobj, outer_resources) -> tuple[list[dict], list[str]]:
    box = [float(v) for v in xobj.get("/BBox", [-1e6, -1e6, 1e6, 1e6])]
    m = tuple(float(v) for v in xobj.get("/Matrix", P.IDENTITY))       # pdfium folds the form's own matrix into its objects
    return _run(ContentStream(xobj, reader), xobj.get("/Resources") or outer_resources, reader, tuple(box), m)


def _get(res, group, name):
    d = res.get_object().get(group) if res is not None else None
    v = d.get_object().get(name) if d is not None else None
    return v.get_object() if v is not None else None


def _is_pattern(res, name) -> bool:
    cs = _get(res, "/ColorSpace", name) if name != "/Pattern" else None
    return name == "/Pattern" or (isinstance(cs, list) and cs and cs[0] == "/Pattern")


def _run(ops, resources, reader, limit, ctm) -> tuple[list[dict], list[str]]:
    events, notes = [], []
    clips, fill_pat, stroke_pat, stack = (), None, False, []
    segs, pending, fill_is_pat, stroke_is_pat, cur = [], None, False, False, (0.0, 0.0)

    def add(kind, **more):
        events.append({"kind": kind, "clips": clips, "limit": limit, **more})

    for operands, op in ops.operations:
        a = operands
        if op == b"q":
            stack.append((ctm, clips, fill_pat, stroke_pat, fill_is_pat, stroke_is_pat))
        elif op == b"Q" and stack:
            ctm, clips, fill_pat, stroke_pat, fill_is_pat, stroke_is_pat = stack.pop()
        elif op == b"cm":
            ctm = P.compose(tuple(float(v) for v in a), ctm)
        elif op == b"cs":
            fill_is_pat, fill_pat = _is_pattern(resources, a[0]), None
        elif op == b"CS":
            stroke_is_pat, stroke_pat = _is_pattern(resources, a[0]), False
        elif op in (b"scn", b"sc"):
            fill_pat = a[-1] if fill_is_pat and a and isinstance(a[-1], str) else None
        elif op in (b"SCN", b"SC"):
            stroke_pat = stroke_is_pat and bool(a) and isinstance(a[-1], str)
        elif op in (b"g", b"rg", b"k"):
            fill_is_pat, fill_pat = False, None
        elif op in (b"G", b"RG", b"K"):
            stroke_is_pat, stroke_pat = False, False
        elif op == b"gs":
            g = _get(resources, "/ExtGState", a[0]) or {}
            sm, bm = g.get("/SMask"), g.get("/BM")
            if (sm is not None and sm != "/None") or (bm is not None and bm not in ("/Normal", "/Compatible")):
                if TRANSPARENCY not in notes:
                    notes.append(TRANSPARENCY)
        elif op == b"m":
            cur = P.apply(ctm, *map(float, a))
            segs.append(("M", *cur))
        elif op == b"l":
            cur = P.apply(ctm, *map(float, a))
            segs.append(("L", *cur))
        elif op in (b"c", b"v", b"y"):
            v = [float(x) for x in a]
            pts = {b"c": v, b"v": [None, None] + v, b"y": v + v[2:]}[op]
            p = [P.apply(ctm, pts[i], pts[i + 1]) if pts[i] is not None else cur for i in (0, 2, 4)]
            segs.append(("C", *p[0], *p[1], *p[2]))
            cur = p[2]
        elif op == b"re":
            x, y, w, h = map(float, a)
            q = [P.apply(ctm, px, py) for px, py in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))]
            segs += [("M", *q[0]), ("L", *q[1]), ("L", *q[2]), ("L", *q[3]), ("Z",)]
            cur = q[0]
        elif op == b"h":
            segs.append(("Z",))
        elif op in (b"W", b"W*"):
            pending = "nonzero" if op == b"W" else "evenodd"
        elif op in FILL | STROKE | {b"n"}:
            if op != b"n" and segs:
                pat = _get(resources, "/Pattern", fill_pat) if op in FILL and fill_pat else None
                add("path", shade=_pattern(pat), tiling=bool(pat) and pat.get("/PatternType") == 1,
                    stroke_pattern=op in STROKE and stroke_pat)
            if pending and segs:
                clips += ((pending, tuple(segs)),)
            segs, pending = [], None
        elif op in SHOW:
            add("text")
        elif op == b"sh":
            add("shading", shade={"shading": _get(resources, "/Shading", a[0]), "matrix": ctm})
        elif op == b"INLINE IMAGE":
            add("image")
        elif op == b"Do":
            x = _get(resources, "/XObject", a[0])
            if x is not None and x.get("/Subtype") == "/Form":
                add("form", xobj=x, resources=resources)
            elif x is not None:
                add("image")
    return events, notes


def _pattern(pat):
    """A shading pattern (type 2) → {"shading", "matrix"}; a tiling pattern → None (pdfium's own object stays)."""
    if pat is None or pat.get("/PatternType") != 2:
        return None
    return {"shading": pat["/Shading"].get_object(), "matrix": tuple(float(v) for v in pat.get("/Matrix", P.IDENTITY))}
