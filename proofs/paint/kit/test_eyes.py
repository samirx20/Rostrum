"""Quick tests for `landed` and `what`. Run: uv run --with numpy --with pillow --with pytest python -m pytest -q test_eyes.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest  # noqa: E402
from doc import Doc  # noqa: E402
import where  # noqa: E402

PATH = [(40, 60, 1), (160, 70, 1), (260, 120, 1)]


@pytest.fixture()
def d():
    d = Doc.new(320, 200, background=(0.1, 0.1, 0.12))
    d.add_layer("sky")
    d.add_layer("ink")
    d.mask_polygon("box", [(20, 20), (300, 20), (300, 180), (20, 180)])
    with d.batch("sky", author="agent:test"):
        d.stroke("sky", [(10, 150, 1), (300, 150, 1)], (0.3, 0.5, 0.9), 30)
    with d.batch("ink line"):
        d.sid = d.stroke("ink", PATH, (0.9, 0.2, 0.2), 14)
    return d


def test_landed_zero_on_own_path(d):
    r = where.landed(d, d.sid)
    assert r["landed"] and r["mean"] < 1.0, r


def test_landed_reports_shifted_path(d):
    shifted = [(x, y + 8, p) for x, y, p in PATH]
    r = where.landed(d, d.sid, path=shifted)
    assert not r["landed"] and 6.5 < r["mean"] < 9.5, r
    assert "missed by" in r["verdict"]


def test_what_names_layer_and_stroke(d):
    t = where.what(d, 100, 66)  # on the ink line
    assert "top painted layer" in t.split("ink")[1].split("\n")[0]
    assert f"id {d.sid}" in t and "'ink line'" in t
    t2 = where.what(d, 100, 150)  # on the sky
    assert "sky" in t2.split("top painted layer")[0].splitlines()[-1]


def test_what_outside_canvas_fails(d):
    with pytest.raises(ValueError):
        where.what(d, 999, 5)
