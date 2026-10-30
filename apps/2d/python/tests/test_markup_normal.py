"""`color="…"` on an SVG part sets currentColor below it, as in a browser (the engine reads color only from CSS)."""
from rostrum2d.markup.normal import svg_color


def test_svg_color_attribute_moves_into_style():
    assert svg_color('<g color="#f00"><rect fill="currentColor"/></g>') == '<g style="color: #f00"><rect fill="currentColor"/></g>'
    assert svg_color('<g style="opacity:.5" color="#f00">') == '<g style="color: #f00; opacity:.5">'


def test_own_style_wins_and_html_untouched():
    assert svg_color('<g style="color:blue" color="#f00">') == '<g style="color:blue">'
    assert svg_color('<div color="#f00">') == '<div color="#f00">'
    assert svg_color('<stop stop-color="#f00"/>') == '<stop stop-color="#f00"/>'
