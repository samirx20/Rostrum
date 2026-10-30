"""Markup films (proof): keys land where an agent expects, values blend, light keeps an element's place. No engine."""
from rostrum2d.markup import Film, Keys, mix
from rostrum2d.markup import apply, light


def test_text_values_blend_number_by_number_and_colours_mix():
    assert mix("M 0 0 L 10 20", "M 10 0 L 30 40", 0.5) == "M 5 0 L 20 30"
    assert mix("blur(2px)", "blur(6px)", 0.25) == "blur(3px)"
    assert mix("M 0 0 L 1 1", "M 0 0 C 1 1 2 2 3 3", 0.5) == "M 0 0 L 1 1"      # different shapes hold
    assert mix("#000000", "#ffffff", 1.0) == "#ffffff"
    k = Keys({0: 0, 1: (100, "linear")})
    assert k(-1) == 0 and k(0.5) == 50 and k(2) == 100


def test_props_go_to_attributes_in_svg_and_css_on_html():
    svg = apply.set_props('<circle id="c" cx="1" r="5"/>', "c", {"cx": 40, "fill": "#f00"})
    assert 'cx="40"' in svg and 'fill="#f00"' in svg
    html = apply.set_props('<div id="d" style="left: 1px"></div>', "d", {"opacity": 0.5, "left": "9px"})
    assert "opacity: 0.5" in html and "left: 9px" in html


def test_keyed_turn_comes_after_the_elements_own_transform():
    """A limb drawn at its joint (translate) turns about that joint: keys never detach it."""
    out = apply.set_props('<g id="fore" transform="translate(0 140)"></g>', "fore", {"rotate": 30})
    assert out.index("translate(0 140)") < out.index("rotate(30)")


def test_a_missing_id_is_reported_and_keys_reach_the_overlay():
    film = Film(duration=1)
    film.scene('<div id="a"></div>')
    film.overlay('<div id="title"></div>')
    film.key("#title", opacity=0.5).key("#nope", opacity=1)
    missing = []
    out = film.markup(0.5, missing)
    assert "opacity: 0.5" in out and missing == ["nope"]


def test_a_lit_svg_keeps_its_class_and_place():
    out = light.apply('<svg class="layer" data-light width="10" height="10"><circle r="3"/></svg>', {})
    assert '<div class="layer" style="filter: url(#rlight1)">' in out
    assert out.count("<circle") == 1 and out.endswith("</div>")
