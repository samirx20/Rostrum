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
