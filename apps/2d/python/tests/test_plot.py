"""What agents rely on to turn numbers into pictures (plot.py, table.py, guides/data-math-and-graphs.md): round axis
ticks, a function's path landing exactly where the data says, gaps where it breaks, a table read as numbers, and the
helpers being there in a script and through inspect_table."""
import math

import pytest
from rostrum_core import Who
from rostrum_core.mcp import Runtime

from rostrum2d import pathdata
from rostrum2d.mcp import app_tools, make_app
from rostrum2d.plot import curve_points, line_d, nice_ticks, plot_area, tick_label, view3d
from rostrum2d.table import parse_table


@pytest.mark.parametrize("lo, hi, extend, want", [
    (0, 1, False, [0, 0.2, 0.4, 0.6, 0.8, 1.0]),
    (-1.3, 7.2, False, [0, 2, 4, 6]),
    (0, 128, True, [0, 50, 100, 150]),
    (0.1, 0.3, False, [0.1, 0.15, 0.2, 0.25, 0.3]),
])
def test_ticks_are_round_and_inside_or_reaching_past_the_range(lo, hi, extend, want):
    got = nice_ticks(lo, hi, 4 if extend else 5, extend=extend)
    assert got == pytest.approx(want)
    assert [tick_label(v, got) for v in got[:2]] == [tick_label(want[0], want), tick_label(want[1], want)]
    assert tick_label(-0.0001, 0.5) == "0.0" and tick_label(1500, 500) == "1500" and tick_label(0.25, 0.05) == "0.25"
    assert tick_label(12500, 2500, separator=",") == "12,500" and tick_label(-1000, 500, " ") == "-1 000"


def test_a_function_path_starts_and_ends_where_the_data_maps_with_y_up():
    P = plot_area(x=(0, 10), y=(-1, 1), rect=(100, 100, 1000, 500))
    assert P(0, -1) == (100, 600) and P(10, 1) == (1100, 100)       # bottom-left, top-right: y grows upward
    for smooth in (False, True):
        cmds = pathdata.commands(line_d(curve_points(lambda x: x / 10, 0, 10, 50), to=P, smooth=smooth))
        assert cmds[0][1:] == pytest.approx((100, 350)) and cmds[-1][-2:] == pytest.approx((1100, 100))
        assert len(cmds) == 50                                       # one M, then one segment per sample: morphs pair up


def test_where_the_function_breaks_the_line_lifts():
    d = line_d(curve_points(lambda x: 1 / x, -1, 1, 5))             # x = 0 divides by zero
    assert [c[0] for c in pathdata.commands(d)] == ["M", "L", "M", "L"]
    assert line_d(curve_points(math.tan, 0, math.pi, 101, ylim=(-5, 5))).count("M") == 2


def test_a_3d_view_maps_axes_as_documented():
    V = view3d(yaw=0, pitch=0, scale=100, center=(0, 0))
    assert V(1, 0, 0) == pytest.approx((100, 0)) and V(0, 0, 1) == pytest.approx((0, -100))


def test_a_table_reads_as_numbers_and_refuses_a_bad_header():
    rows = parse_table("year;value;note\n2020;1.5;a\n\n2021;12;\n")
    assert rows == [{"year": 2020, "value": 1.5, "note": "a"}, {"year": 2021, "value": 12, "note": ""}]
    with pytest.raises(ValueError, match="header"):
        parse_table("a,a\n1,2")


def test_scripts_have_the_helpers_and_inspect_table_reads_a_file(tmp_path):
    (tmp_path / "data.csv").write_text("name,score\nA,42\nB,97\n", encoding="utf-8")
    rt = Runtime(app := make_app(str(tmp_path), ["demo"]), app_tools())
    reply, _ = rt.call("inspect_table", {"path": "data.csv"}, Who.agent("t"))
    assert reply["ok"], reply
    data = reply["data"]
    assert data["rows"] == [{"name": "A", "score": 42}, {"name": "B", "score": 97}]
    assert data["columns"][1] == {"name": "score", "min": 42, "max": 97, "ticks": [0, 20, 40, 60, 80, 100]}
    src = ('comp("c", width=400, height=300, duration=1)\nP = plot_area(x=(0, 1), y=(0, 1), rect=(0, 0, 400, 300))\n'
           'path("f", d=line_d(curve_points(lambda x: x * x, 0, 1, 20), to=P), fill="none", stroke=True)\n')
    rt.call("run_script", {"source": src, "name": "s.py"}, Who.agent("t"))
    assert next(iter(app.documents.values())).item("f")["d"].startswith("M")
