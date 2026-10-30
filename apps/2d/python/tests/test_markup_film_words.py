"""Film words agents reach for as they write them: values in the listed order, motion blur keyed and kept inside a shot."""
import pytest

from rostrum2d.markup import Film


def test_grain_and_light_take_values_in_order():
    f = Film(duration=2).grain(.06, 1.6).light(30, 50)
    assert (f._grain["amount"](0), f._grain["size"](0), f._light["angle"](0), f._light["elevation"](0)) == (.06, 1.6, 30, 50)
    with pytest.raises(ValueError, match="at most"):
        Film().grain(*range(9))


def test_blur_shutter_keys_turn_it_off_for_a_stretch():
    f = Film(duration=4).blur({0: 180, 2: (0, "hold")}, 4)
    assert len(f.samples(1.0)) == 4 and f.samples(3.0) == []


def test_blur_samples_stay_inside_their_shot():
    f = Film(duration=4, fps=10)
    f.scene(lambda t: f"<p>{'A' if t < 2 else 'B'}</p>")
    f.blur(360, 5).cut(2)
    assert all("A" in m for m in f.samples(1.99)) and all("B" in m for m in f.samples(2.0))


def test_data_depth_keys_are_attributes_on_html_too():
    f = Film(duration=2)
    f.scene('<div id="hills" data-depth="0.3" style="position:absolute"></div>')
    f.key("#hills", data_depth={0: 0.3, 2: (0.7, "linear")})
    assert 'data-depth="0.5"' in f.markup(1.0)


def test_data_blur_off_holds_an_element_at_the_frame_moment_while_the_rest_moves():
    f = Film(duration=4, fps=10)
    f.scene('<div id="bg" style="left:0px"></div><h1 id="title" data-blur="off" style="left:0px"><b>T</b></h1>')
    f.key("#bg", left={0: 0, 4: (400, "linear")}).key("#title", left={0: 0, 4: (400, "linear")})
    f.blur(360, 5)
    samples = f.samples(2.0)
    bgs = {s.split('id="bg"')[1].split('px')[0] for s in samples}
    titles = {s.split('id="title"')[1].split("</h1>")[0] for s in samples}
    assert len(bgs) == 5, "the rest keeps the film's blur"
    assert len(titles) == 1 and "left: 200px" in titles.pop().replace(":200", ": 200"), "the title is drawn sharp, at the frame's moment"


def test_data_blur_degrees_give_an_element_its_own_shorter_shutter():
    f = Film(duration=4, fps=10)
    f.scene('<i id="a" data-blur="90" style="left:0px"></i>')
    f.key("#a", left={0: 0, 4: (400, "linear")})
    f.blur(360, 3)
    lefts = [float(s.split("left")[1].split("px")[0].strip(": ")) for s in f.samples(2.0)]
    assert lefts == pytest.approx([198.75, 200.0, 201.25]), lefts  # 90 of 360 degrees: a quarter of the film's ±5 px
