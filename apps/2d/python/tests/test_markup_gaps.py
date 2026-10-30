"""Run notes name only what the engine does not draw: SVG filters on shapes inside an <svg> and feDropShadow are drawn
now (no note); lighting primitives still pass their input through, and an feImage inside an <svg>-shape filter draws nothing."""
from rostrum2d.markup.gaps import notes

SVG = '<svg width="100" height="100"><defs><filter id="f">{}</filter></defs><rect width="50" height="50" filter="url(#f)"/></svg>'


def test_svg_filters_on_shapes_and_drop_shadows_get_no_note():
    assert notes(SVG.format('<feGaussianBlur stdDeviation="4"/>')) == []
    assert notes(SVG.format('<feDropShadow dx="4" dy="4"/>')) == []


def test_primitives_not_drawn_yet_are_named():
    assert any("feDiffuseLighting" in n for n in notes(SVG.format('<feDiffuseLighting><feDistantLight/></feDiffuseLighting>')))
    assert any("feImage" in n for n in notes(SVG.format('<feImage href="a.png"/>')))
    # On a <div>'s url() filter feImage is drawn: no note.
    div = '<svg width="0" height="0"><defs><filter id="f"><feImage href="a.png"/></filter></defs></svg><div style="filter:url(#f)"></div>'
    assert notes(div) == []
