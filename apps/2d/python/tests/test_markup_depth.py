"""Markup depth: data-depth splits the world into camera boxes in paint order, each moved by the camera at its depth
and blurred by its distance from focus. No engine."""
import re

import pytest

from rostrum2d.markup import apply, depth

W, H = 1920, 1080
CAM = {"x": 1160, "y": 440, "zoom": 2, "rotate": 5}


def _today(world, cam):
    """Film.markup's single camera box before depth (the reference the d = 1 world must keep)."""
    x, y, z, r = cam.get("x", W / 2), cam.get("y", H / 2), cam.get("zoom", 1), cam.get("rotate", 0)
    tr = f"translate({W / 2:.3f}px, {H / 2:.3f}px) scale({z:.5f}) rotate({-r:.4f}deg) translate({-x:.3f}px, {-y:.3f}px)"
    return (f'<div id="rostrum-camera" style="position:absolute; left:0; top:0; width:{W}px; height:{H}px; '
            f'transform-origin: 0 0; transform: {tr}">{world}</div>')


def test_a_world_without_depth_is_exactly_todays_single_box():
    world = '<div class="sky"></div><svg width="10"><rect id="a"/></svg>'
    assert depth.camera_wrap(world, CAM, W, H) == _today(world, CAM)
    assert depth.camera_wrap(world, {"zoom": 1.3}, W, H) == _today(world, {"zoom": 1.3})


def test_split_keeps_paint_order_and_joins_neighbours_at_one_depth():
    world = ('<div id="sky" data-depth="0"></div><div id="far" data-depth="0.4"><p>x</p></div>'
             '<div id="near" data-depth="0.4"></div><img id="i" src="a.png"><div id="fg" data-depth="1.6"></div>')
    runs = depth.split(world)
    assert [d for d, _ in runs] == [0, 0.4, 1, 1.6]
    assert "".join(s for _, s in runs) == world
    assert 'id="far"' in runs[1][1] and 'id="near"' in runs[1][1]


def test_depth_one_moves_exactly_like_the_world_and_zero_is_fixed_to_the_screen():
    assert depth.transform(CAM, W, H, 1) == depth.transform(CAM, W, H)
    fixed = depth.transform({"x": 1160, "y": 440, "zoom": 2}, W, H, 0)
    assert fixed == "translate(960.000px, 540.000px) scale(1.00000) rotate(0.0000deg) translate(-960.000px, -540.000px)"
    half = depth.transform({"x": 1160, "y": 440, "zoom": 4}, W, H, 0.5)
    assert "scale(2.00000)" in half and "translate(-1060.000px, -490.000px)" in half
    front = depth.transform({"x": 1160, "zoom": 0.5}, W, H, 3)     # zoom ** d never reaches 0 or turns over
    assert "scale(0.12500)" in front and "translate(-1560.000px" in front


def test_each_depth_gets_its_own_box_in_order_with_its_own_move():
    world = '<div id="far" data-depth="0.5"></div><div id="mid"></div><div id="fg" data-depth="2"></div>'
    out = depth.camera_wrap(world, CAM, W, H)
    trs = re.findall(r"transform: ([^\"]+)\">", out)
    assert trs == [depth.transform(CAM, W, H, d) for d in (0.5, 1, 2)]
    assert out.index('id="far"') < out.index('id="mid"') < out.index('id="fg"')
    assert 'id="rostrum-camera"' not in out and "filter" not in out


def test_direct_children_of_a_top_level_svg_split_into_copies_with_defs_kept():
    world = ('<svg width="1920" height="1080" style="position:absolute"><defs><linearGradient id="g"/></defs>'
             '<g id="hills" data-depth=".3"><path/></g><g id="road"/><g id="post" data-depth="1.5"/></svg>')
    runs = depth.split(world)
    assert [d for d, _ in runs] == [0.3, 1, 1.5]
    for (_, s), ident in zip(runs, ("hills", "road", "post")):
        assert s.startswith('<svg width="1920" height="1080" style="position:absolute"><defs>') and s.endswith("</svg>")
        assert f'id="{ident}"' in s and s.count("<g id=") == 1


def test_focus_and_aperture_blur_each_depth_in_screen_pixels():
    world = '<div data-depth="0.5"></div><div></div><div data-depth="2"></div>'
    out = depth.camera_wrap(world, {**CAM, "focus": 1, "aperture": 8}, W, H)
    assert re.findall(r"filter: blur\(([\d.]+)px\)", out) == ["4.00", "8.00"]     # in focus (d = 1): no blur box
    assert depth.blur_px({"focus": 1}, 3) == 0 and depth.blur_px({"aperture": 9}, 3) == 0
    whole = depth.camera_wrap("<p/>", {"focus": 0, "aperture": 6}, W, H)            # no data-depth: the world at 1
    assert whole.startswith('<div style="position:absolute; left:0; top:0; width:1920px; height:1080px; filter: blur(6.00px)">')


def test_a_keyed_data_depth_is_read_as_the_markup_has_it_at_that_frame():
    world = '<svg width="10"><g id="hill" data-depth="0.2"/><g id="tree"/></svg>'
    keyed = apply.set_props(world, "hill", {"attr:data-depth": 0.7})
    assert [d for d, _ in depth.split(keyed)] == [0.7, 1]
    html = apply.set_props('<div id="hill"></div>', "hill", {"attr:data-depth": 0.25})
    assert [d for d, _ in depth.split(html)] == [0.25]


def test_a_depth_that_is_not_a_number_is_named():
    with pytest.raises(ValueError, match='data-depth="far"'):
        depth.split('<div data-depth="far"></div>')
