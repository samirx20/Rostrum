"""Markup light per part and grain: an <svg> with lit parts splits into stacked copies in paint order, one lit layer
per part; grain lands as the engine's grain shader. No engine."""
import re

from rostrum2d.markup import Film, light

SVG = ('<svg data-light width="100" height="100" style="position:absolute; left:5px; opacity:.5">'
       '<defs><linearGradient id="g"/></defs><rect id="body"/><g id="arm" transform="translate(4 4)"><rect/></g></svg>')


def _copies(out: str) -> list[str]:
    return re.findall(r"<svg width=\"100\"[^>]*>.*?</svg>", out)


def test_whole_svg_light_gives_one_lit_layer_per_direct_child_in_paint_order():
    out = light.apply(SVG, {})
    copies = _copies(out)
    assert len(copies) == 2 and out.count("filter: url(#rlight") == 2
    assert 'id="body"' in copies[0] and 'id="arm"' not in copies[0]
    assert 'id="arm" transform="translate(4 4)"' in copies[1] and 'id="body"' not in copies[1]
    assert all('id="g"' in c for c in copies)                    # definitions in every copy
    assert "data-light" not in out
    box = out[out.index("</defs></svg>") + len("</defs></svg>"):]
    assert box.startswith('<div style="position: absolute; left: 5px; opacity: .5">')   # the svg's place and opacity


def test_a_lit_part_deep_inside_splits_the_svg_around_it():
    src = ('<svg width="100" height="100"><rect id="a"/><g id="pose" transform="rotate(5)"><rect id="b"/>'
           '<path id="hand" data-light="soft: 8"/><rect id="c"/></g><rect id="d"/></svg>')
    out = light.apply(src, {})
    copies = _copies(out)
    assert len(copies) == 3 and out.count("filter: url(#rlight") == 1
    assert 'id="a"' in copies[0] and 'id="b"' in copies[0] and 'id="hand"' not in copies[0]
    assert 'id="pose" transform="rotate(5)"' in copies[1] and 'id="hand"' in copies[1] and 'id="b"' not in copies[1]
    assert 'id="c"' in copies[2] and 'id="d"' in copies[2]
    assert 'stdDeviation="8"' in out                             # the part's own settings


def test_an_svg_without_light_is_untouched():
    src = '<svg width="10" height="10"><rect/></svg><div data-light></div>'
    out = light.apply(src, {})
    assert src.split("<div")[0] in out and out.count("rlight1") == 2


def test_grain_lands_on_elements_on_lit_ones_inside_their_light_and_on_the_frame():
    film = Film(200, 100, duration=1)
    film.scene('<div data-grain="amount: .3; size: 2"></div><div data-light data-grain></div>')
    film.grain(amount={0: 0.1, 1: 0.3})
    out = film.markup(0.5)
    assert out.count('effect="grain"') == 3                      # the div, the lit div's light, the whole frame
    lit = re.search(r'<filter id="rlight1".*?</filter>', out, re.S).group(0)
    assert 'effect="grain"' in lit and "frame 15" in lit         # a new grain each frame
    assert "amount 0.2" in out                                   # keyed frame grain
    assert "data-grain" not in out
