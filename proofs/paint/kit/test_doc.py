"""Guards what agents rely on: exact replay, exact undo / redo, history rules, loud failures, 'which stroke'."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pytest
from brush import curve
from doc import Doc


def _paint(d):
    d.add_layer("sky")
    road = d.mask_polygon("road", [(10, 60), (110, 60), (110, 90), (10, 90)], feather=1)
    with d.batch("block in", author="agent:test"):
        d.gradient("sky", (0, 0), (0, 60), (0.3, 0.5, 0.8), (0.9, 0.8, 0.7))
        d.fill_region("sky", road, (0.4, 0.4, 0.4), 8, angle=10, seed=3, grain=0.3)
    with d.batch("strokes"):
        a = d.stroke("sky", curve((5, 20), (60, 10), (115, 30), pressure=(0.3, 1, 0.2)), (0.8, 0.3, 0.2), 10,
                     brush="bristle", seed=1, hue_jitter=6)
        b = d.stroke("sky", curve((20, 40), (100, 45)), (0.1, 0.1, 0.1), 3, brush="line", seed=2)
        d.stroke("sky", curve((30, 10), (40, 80)), (0, 0, 0), 12, brush="round", wet=0.6, sample_all=True, seed=4)
        d.stroke("sky", curve((80, 20), (90, 80)), (0, 0, 0), 9, brush="block", mode="erase", mask=road.inverted())
    return a, b


def test_replay_gives_identical_pixels(tmp_path):
    d = Doc.new(120, 100, background=(0.9, 0.9, 0.85))
    _paint(d)
    d.save(tmp_path / "t.paint.json")
    e = Doc.open(tmp_path / "t.paint.json")
    assert np.array_equal(d.composite(), e.composite())
    assert np.array_equal(d.s.last, e.s.last)


def test_undo_then_redo_identical_and_new_batch_drops_redo():
    d = Doc.new(120, 100)
    _paint(d)
    after, before = d.composite(), d.snapshot(len(d.history()) - 2)
    d.undo()
    assert np.array_equal(d.composite(), before)
    d.redo()
    assert np.array_equal(d.composite(), after)
    d.undo()
    d.fill("sky", (1, 0, 0), opacity=0.1)
    with pytest.raises(IndexError):
        d.redo()


def test_locked_layer_and_bad_input_fail_loudly():
    d = Doc.new(50, 50)
    d.add_layer("ink")
    d.set_layer("ink", locked=True)
    with pytest.raises(PermissionError):
        d.stroke("ink", [(1, 1), (20, 20)], (0, 0, 0), 4)
    with pytest.raises(KeyError):
        d.stroke("nope", [(1, 1), (20, 20)], (0, 0, 0), 4)
    with pytest.raises(ValueError):
        d.stroke("background", [(1, 1), (20, 20)], (0, 0, 0), 4, brush="sponge")
    with pytest.raises(ValueError):
        d.mask_polygon("off", [(-30, -30), (-10, -30), (-10, -10)])
    with pytest.raises(PermissionError):  # a failed batch is rolled back whole
        with d.batch("half"):
            d.fill("background", (1, 0, 0))
            d.fill("ink", (0, 1, 0))
    assert d.history()[-1]["label"] == "set_layer" and d.composite()[0, 0, 1] == 1.0


def test_top_stroke_at_returns_the_last_stroke():
    d = Doc.new(100, 60)
    a = d.stroke("background", [(10, 30), (90, 30)], (1, 0, 0), 10, brush="round", hardness=0.9)
    b = d.stroke("background", [(50, 5), (50, 55)], (0, 0, 1), 10, brush="round", hardness=0.9)
    assert d.top_stroke_at(20, 30) == a and d.top_stroke_at(50, 30) == b and d.top_stroke_at(5, 5) is None
    assert d.stroke_coverage(a)[30, 20] > 0.9 and d.stroke_info(b)["brush"] == "round"
    d.undo()
    assert d.top_stroke_at(50, 30) == a
