"""Round 2d-why-still-broken: a script's group placed by x / y alone is a point its children count from (a robot arm of
nested joint groups landed off screen when they counted from a hidden 1920 x 1080 box), and a layer made riding a path
sits on it (x / y given to it are an offset; a dot given the frame's centre landed 1100 px off its curve, silently)."""
import pytest
from rostrum_core import Document
from rostrum_core.tree import walk

from fake_layout import FakeEngine
from rostrum2d import KIND, textsize
from rostrum2d.mcp import geometry as G
from rostrum2d.script import run_source


@pytest.fixture(autouse=True)
def fake_engine():
    with textsize.use(FakeEngine()):
        yield


def boxes(body, t=0.5):
    root = run_source('comp("main", width=1920, height=1080, duration=4)\n' + body, "s.py", Document.new(KIND))
    comp = next(c for c in root["comps"] if c["id"] == "main")
    return {n["id"]: G.aabb(n["corners"]) for n in G.flatten(comp, t)}


def test_children_of_a_group_placed_by_x_y_count_from_that_point_and_nested_groups_turn_on_it():
    b = boxes('with group("arm", x=520, y=650):\n'
              '    shape("base", shape="rect", w=120, h=60, x=0, y=80)\n'
              '    with group("shoulder", x=0, y=0) as s:\n'
              '        shape("link", shape="rect", w=20, h=100, x=0, y=-50)\n'
              '    s.key("rotation", {0: 0, 1: 90})\n', t=1.0)
    assert b["base"] == pytest.approx((460, 700, 580, 760), abs=0.5)
    x0, y0, x1, y1 = b["link"]                     # turned 90 degrees on the shoulder point (520, 650): lies to its right
    assert (x0, y0, x1, y1) == pytest.approx((520, 640, 620, 660), abs=0.5)


def test_a_group_without_x_y_keeps_its_children_where_they_are_written():
    b = boxes('with group("sec", start=0, end=4):\n    shape("s", shape="rect", w=100, h=100, x=300, y=200)\n')
    assert b["s"] == pytest.approx((250, 150, 350, 250), abs=0.5)


def test_a_rider_sits_on_its_path_and_a_given_x_y_is_its_offset_never_refused():
    b = boxes('path("line", d="M 100 500 L 900 500", stroke=True, fill="none")\n'
              'shape("dot", shape="ellipse", w=20, h=20, ridePath="line", rideAt="end")\n')
    assert b["dot"] == pytest.approx((890, 490, 910, 510), abs=1)
    far = boxes('path("line", d="M 100 500 L 900 500", stroke=True, fill="none")\n'
                'shape("dot", shape="ellipse", w=20, h=20, ridePath="line", rideAt="end", x=960, y=540)\n')
    assert far["dot"] == pytest.approx((1850, 1030, 1870, 1050), abs=1)    # what the script wrote: the end + (960, 540)
