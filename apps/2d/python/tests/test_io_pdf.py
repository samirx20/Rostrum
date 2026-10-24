"""PDF import: one composition per page, and a shading or a clip path either comes across or is named in the report."""
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, NumberObject, StreamObject
from rostrum_core import Document
from rostrum_core.who import Who

from rostrum2d.io import importing
from rostrum2d.io.pdf import pdf_pages
from rostrum2d.kind import KIND

ME = Who.agent("test")


def _page(w, content, shadings=None):
    page = w.add_blank_page(200, 100)
    stream = StreamObject()
    stream.set_data(content.encode())
    res = DictionaryObject()
    if shadings:
        res[NameObject("/Shading")] = DictionaryObject({NameObject(f"/{k}"): v for k, v in shadings.items()})
    page[NameObject("/Resources")], page[NameObject("/Contents")] = res, w._add_object(stream)


def _axial():
    fn = DictionaryObject({NameObject("/FunctionType"): NumberObject(2), NameObject("/Domain"): ArrayObject([FloatObject(0), FloatObject(1)]),
                           NameObject("/C0"): ArrayObject([FloatObject(1), FloatObject(0), FloatObject(0)]),
                           NameObject("/C1"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(1)]), NameObject("/N"): NumberObject(1)})
    return DictionaryObject({NameObject("/ShadingType"): NumberObject(2), NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                             NameObject("/Coords"): ArrayObject([FloatObject(c) for c in (0, 0, 200, 0)]), NameObject("/Function"): fn})


def test_each_page_is_a_composition_and_nothing_is_dropped_unsaid(tmp_path):
    w = PdfWriter()
    _page(w, "q 10 10 100 60 re W n /G sh Q", {"G": _axial()})                            # gradient inside a clip
    _page(w, "q 20 20 m 150 20 l 80 90 l h W n 1 0 0 rg 0 0 200 100 re f Q")             # a triangle clip on a rectangle
    _page(w, "/M sh", {"M": DictionaryObject({NameObject("/ShadingType"): NumberObject(4)})})   # a shading pdfium can not use: must be said
    w.write(tmp_path / "t.pdf")
    trees = pdf_pages(tmp_path / "t.pdf")
    assert [t["comp"] for t in trees] == ["Page 1", "Page 2", "Page 3"]
    assert trees[0]["layers"][0]["effects"][0]["props"]["style"] == "linear"          # a rectangle clip that cuts nothing is dropped
    assert any(n.get("matte") for n in trees[1]["layers"]) and trees[1]["layers"][-1]["layers"][0]["props"]["fill"] == "#ff0000ff"
    assert any("not carried over" in line for line in trees[2]["report"])
    doc = Document.new(KIND, folder=tmp_path)
    doc.apply([{"op": "comp.add", "args": {"id": "c", "width": 200, "height": 100}}], ME)
    r = importing.run(doc, ME, "c", tmp_path / "t.pdf", page=0)
    assert r["comps"] == ["page_1", "page_2", "page_3"] and len(doc.data["comps"]) == 4


def test_bold_and_italic_come_from_the_font_name_or_descriptor():
    from rostrum2d.io.pdf_font import style_of
    assert style_of("ABCDEF+Inter-SemiBoldItalic", 0, 0, 0) == ("Inter", 600.0, -12.0)
    assert style_of("Arial,Bold", 0, 0, 435) == ("Arial", 700.0, 0.0)              # a stem-derived 435 is not read as a weight
    assert style_of("Unnamed", 1 << 18, 0, 0)[1] == 700.0 and style_of("Unnamed", 64, -9, 400)[2] == -9.0


def test_text_in_pieces_comes_in_as_one_text_layer_per_line(tmp_path):
    w = PdfWriter()
    _page(w, "BT /F1 20 Tf 10 60 Td (He) Tj ET BT /F1 20 Tf 31 60 Td (llo) Tj ET BT /F1 20 Tf 70 60 Td (you) Tj ET "
             "BT /F1 20 Tf 10 20 Td (Second line) Tj ET")
    page = w.pages[0]
    page["/Resources"][NameObject("/Font")] = DictionaryObject({NameObject("/F1"): DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})})
    w.write(tmp_path / "t.pdf")
    texts = [n for n in pdf_pages(tmp_path / "t.pdf")[0]["layers"] if n["type"] == "text"]
    assert [t["props"]["body"].strip() for t in texts] == ["Hello you", "Second line"]
