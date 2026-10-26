"""The forms agents write by habit become the one real field (script_words.py), and what is ambiguous still fails loudly."""
import pytest

from rostrum_core.errors import RostrumError
from rostrum2d import run_source

HEAD = 'comp("main", width=1920, height=1080, fps=30, duration=4)\n'


def layer(src):
    return run_source(HEAD + src, "t.py")["comps"][0]["layers"][-1]


def test_habit_words_become_the_real_fields():
    s = layer('shape("a", shape="circle", width=300, fill="#fA0", stroke="#fff", steps=2, borderRadius=4)')
    assert (s["shape"], s["w"], s["fill"], s["stroke"], s["strokeColor"], s["timing"], s["radius"]) == \
        ("ellipse", 300, "#ffAA00", True, "#ffffff", "2", 4)
    t = layer('text("t", text="Hi", fontSize=80, fill="#123", textAlign="centre")')
    assert (t["body"], t["size"], t["color"], t["align"]) == ("Hi", 80, "#112233", "center")
    assert layer('path("p", d="M 0 0 L 9 9", fill="none", stroke=True)')["filled"] is False
    k = layer('shape("a").key("x", {0: 0, 1: 100}, ease="ease-out")')["keys"][0]
    assert k["ease"] == "easeOut"


def test_a_path_with_no_box_is_where_its_points_say():
    p = layer('path("p", d="M 360 600 L 1560 300", fill="none", stroke=True)')
    assert (p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["w"], p["h"]) == (360, 300, 1200, 300)
    assert p["d"] == "M 0 300 L 1200 0"


@pytest.mark.parametrize("src, says", [
    ('shape("a", fill="green")', '"#008000"'),                 # a CSS name: hinted, never taken
    ('shape("a", fill="#ffffff80")', "opacity"),
    ('shape("a", opacity=100)', "Write 1"),
    ('shape("a").key("x", {"beat": 0})', '"#beat"'),
    ('with group("g"):\n    shape("m")\nshape("a", matte="m")', "beside"),
    ('rect("a")', 'shape(id, shape="rect"'),
])
def test_what_is_not_clear_fails_saying_what_to_write(src, says):
    with pytest.raises(RostrumError) as e:
        run_source(HEAD + src, "t.py")
    assert says in str(e.value)


def test_a_field_written_as_an_attribute_is_set_or_refused_never_dropped():
    t = layer('t = text("t", body="Hi")\nt.end = 3\nt.start = 1\nt.x = t.x + 10')
    assert (t["start"], t["end"], t["x"]) == (1, 3, 970)
    for bad in ('t.ned = 3', 't.key = 3', 'y = t.ned', 'p = painted("g")\np.scale = 2'):
        with pytest.raises(RostrumError):
            layer('t = text("t")\n' + bad)
