"""lower_third and chart (ui_lower_third.py, ui_chart.py): what would break silently: a lower third in a container
is placed by it (no x / y of its own), at the top level it sits in the lower-left safe area; its in / out keys stay
on the marker; a chart's axis ends on a round number at or above the biggest value, its bars scale to it, and its
text grows with the width it is made in."""
import pytest
from rostrum_core import Document, markers as M
from rostrum_core.tree import walk
from rostrum_core.who import Who

from fake_layout import FakeEngine
from rostrum2d import KIND, textsize
from rostrum2d.script import run_source


@pytest.fixture(autouse=True)
def fake_engine():
    with textsize.use(FakeEngine()):
        yield


def items(body, folder=None):
    d = Document.new(KIND)
    d.folder = folder
    root = run_source('comp("main", width=1920, height=1080, duration=10)\n' + body, "s.py", d)
    return {n["id"]: n for n in walk(root, KIND.lists) if "id" in n}


def test_a_lower_third_in_a_container_is_placed_by_it_and_at_the_top_level_sits_lower_left():
    got = items('with device("ph"):\n    lower_third("Ana", role="Host", id="in")\nlower_third("Ben", role="Guest", id="top")\n')
    assert not got["in"].get("layoutApart")                 # placed by the screen's column, not set apart
    assert got["in"].get("alignSelf") == "start"
    top = got["top"]
    assert (top["anchorX"], top["anchorY"]) == (0, 1)
    assert top["x"] == pytest.approx(1920 * 0.08) and top["y"] == pytest.approx(1080 * 0.9)
    assert got["top_name"]["body"] == "Ben" and got["top_role"]["body"] == "Guest"


def test_lower_third_keys_land_on_the_marker(tmp_path):
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "intro", "at": 2.0}}], Who.person("sam"))
    got = items('lower_third("Ana", id="lt", at="#intro+0.2", out="#intro+4")\n'
                'with device("ph"):\n    lower_third("Bo", id="lt2", at=1, enter="below")\n', tmp_path)
    x_keys = [k for k in got["lt"]["keys"] if k["prop"] == "x"]
    assert x_keys[0]["t"] == "#intro+0.2" and x_keys[-2]["t"] == "#intro+4"
    assert x_keys[0]["v"] < x_keys[1]["v"] == pytest.approx(1920 * 0.08)          # in from the left
    assert {k["prop"] for k in got["lt"]["keys"]} == {"opacity", "x"}
    inner = {k["prop"] for k in got["lt2"]["keys"]}
    assert inner == {"opacity", "shiftY"}                                           # the layout keeps its place


def test_chart_axis_ends_on_a_round_number_above_the_biggest_value_and_bars_scale_to_it():
    got = items('chart([12, 37, 21], labels=["a", "b", "c"], id="c", w=600, h=300, x=100, y=100)\n')
    ticks = [float(got[f"c_y{i}"]["body"]) for i in range(10) if f"c_y{i}" in got]
    assert ticks[0] == 0 and ticks[-1] >= 37 and ticks[-1] in (40, 50)
    h0, h1 = got["c_bar0"]["h"], got["c_bar1"]["h"]
    assert h1 / h0 == pytest.approx(37 / 12) and h1 < 300


def test_chart_text_grows_with_the_room_it_is_made_in():
    got = items('with device("ph"):\n    chart([1, 2], id="small")\n'
                'with device("lap", kind="laptop"):\n    chart([1, 2], id="big")\n')
    assert got["big_y0"]["size"] > got["small_y0"]["size"] * 1.4
    assert 9 <= got["small_y0"]["size"] <= 16


def test_chart_at_grows_bars_from_that_time():
    got = items('chart([3, 4], id="c", x=0, y=0, w=400, at=1.5, stagger=0.1)\n')
    k0 = [k for k in got["c_bar0"]["keys"] if k["prop"] == "scaleY"]
    k1 = [k for k in got["c_bar1"]["keys"] if k["prop"] == "scaleY"]
    assert (k0[0]["t"], k0[0]["v"], k1[0]["t"]) == (1.5, 0.0, pytest.approx(1.6))
