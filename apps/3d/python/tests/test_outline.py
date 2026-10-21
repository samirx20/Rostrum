"""Text and SVG outlines: holes nest under their outers, orientation, and loud errors."""
import pytest

from rostrum3d import compile as C, outline as O


def _item(**kw):
    base = {"id": "m", "type": "mesh", "shape": "text", "text": "Ob", "font": "Inter", "weight": 400, "size": 0.1,
            "tracking": 0.0, "lineHeight": 1.2, "align": "center", "svgFile": "", "pathData": "", "svgWidth": 1.0,
            "doc2d": "", "layer": ""}
    return {**base, **kw}


def _area(p):
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(p, p[1:] + p[:1]))


def test_text_has_outers_with_holes():
    shapes = O.for_item(_item())
    assert len(shapes) == 2 and [len(s["holes"]) for s in shapes] == [1, 1]
    assert all(_area(s["outer"]) > 0 and _area(h) < 0 for s in shapes for h in s["holes"])
    xs = [p[0] for s in shapes for p in s["outer"]]
    assert min(xs) < 0 < max(xs)                      # centred on the item origin


def test_svg_square_with_square_hole():
    d = "M0 0H10V10H0Z M3 3V7H7V3Z"                   # same winding twice would fill the hole; nonzero + opposite = hole
    shapes = O.for_item(_item(shape="svg", pathData=d, svgWidth=0.5))
    assert len(shapes) == 1 and len(shapes[0]["holes"]) == 1 and len(shapes[0]["outer"]) == 4


def test_loud_errors():
    with pytest.raises(ValueError, match="unknown font.*Inter"):
        O.for_item(_item(font="Nope"))
    with pytest.raises(ValueError, match="empty"):
        O.for_item(_item(text="  "))
    with pytest.raises(ValueError, match="no path layer"):
        import tempfile, pathlib, json
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "docs").mkdir()
            (pathlib.Path(tmp) / "docs" / "ui.mtn").write_text(json.dumps({"doc": {"id": "root", "layers": []}}))
            O.for_item(_item(shape="path2d", doc2d="ui", layer="p1"), tmp)


def test_compiler_sends_outline_shape():
    props = {"shape": "text", "depth": 0.02, "text": "x", "font": "Inter"}
    C._outline_props("m", _item(), props, None)
    assert props["shape"] == "outline" and props["outline"] and "text" not in props and "font" not in props
