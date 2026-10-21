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
    assert d.history()[-1]["label"] == "setup" and d.composite()[0, 0, 1] == 1.0


def test_top_stroke_at_returns_the_last_stroke():
    d = Doc.new(100, 60)
    a = d.stroke("background", [(10, 30), (90, 30)], (1, 0, 0), 10, brush="round", hardness=0.9)
    b = d.stroke("background", [(50, 5), (50, 55)], (0, 0, 1), 10, brush="round", hardness=0.9)
    assert d.top_stroke_at(20, 30) == a and d.top_stroke_at(50, 30) == b and d.top_stroke_at(5, 5) is None
    assert d.stroke_coverage(a)[30, 20] > 0.9 and d.stroke_info(b)["brush"] == "round"
    d.undo()
    assert d.top_stroke_at(50, 30) == a


def test_cache_hit_gives_replay_pixels_and_exact_undo(tmp_path, capsys):
    p = tmp_path / "c.paint.json"
    d = Doc.new(120, 100, background=(0.9, 0.9, 0.85))
    _paint(d)
    d.save(p)
    e = Doc.open(p)  # from the cache: no replay note
    assert "replaying" not in capsys.readouterr().err
    r = Doc.open(p, use_cache=False)
    assert np.array_equal(e.composite(), r.composite()) and np.array_equal(e.s.last, r.s.last)
    assert np.array_equal(e.stroke_coverage(2), r.stroke_coverage(2)) and e.history() == r.history()
    e.undo()  # from a kept earlier state in the cache
    r.undo()
    assert np.array_equal(e.composite(), r.composite())
    e.save(p)
    f = Doc.open(p)
    assert "replaying" not in capsys.readouterr().err and len(f._redo) == 1  # redo is saved in the document
    f.redo()
    assert np.array_equal(f.composite(), d.composite())
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(" ")  # same ops: still a hit
    Doc.open(p)
    assert "replaying" not in capsys.readouterr().err


def test_stale_cache_replays_and_says_so(tmp_path, capsys):
    p = tmp_path / "s.paint.json"
    d = Doc.new(60, 40)
    d.fill("background", (1, 0, 0))
    d.save(p)
    import json
    data = json.loads(p.read_text())
    data["batches"][0]["ops"][0]["color"] = [0, 0, 1]
    p.write_text(json.dumps(data))
    e = Doc.open(p)
    assert "out of date" in capsys.readouterr().err and e.composite()[0, 0, 2] == 1.0


def test_old_gradient_op_replays_as_before():
    d = Doc.new(100, 100, background=(0, 0, 0))
    with d.batch("old"):  # a v1 op as older documents hold it: fills the whole layer, clamps to c1 outside
        d._do(dict(op="gradient", layer="background", p0=[50, 50], p1=[60, 50], c0=[1, 1, 1], c1=[0.2, 0.4, 0.6],
                   mask=None, opacity=1.0, mode="normal", shape="radial"))
    assert np.allclose(d.composite()[5, 5], (0.2, 0.4, 0.6)) and np.allclose(d.composite()[50, 50], 1)


def test_new_gradient_paints_only_where_it_is_and_light_modes():
    d = Doc.new(100, 100, background=(0.5, 0, 0))
    d.gradient("background", (50, 50), (60, 50), (1, 1, 1, 1), (1, 1, 1, 0), shape="radial")
    c = d.composite()
    assert np.allclose(c[5, 5], (0.5, 0, 0)) and np.allclose(c[50, 50], 1) and 0.5 < c[50, 55, 0] < 1
    d.add_layer("glow", mode="screen")
    d.gradient("glow", (0, 0), (100, 0), (0, 0.5, 0), (0, 0.5, 0), mode="screen", opacity=0.5)
    d.gradient("glow", (0, 0), (100, 0), (0, 0.5, 0), (0, 0.5, 0), mode="screen", opacity=0.5)
    g = d.layer_pixels("glow")
    assert np.allclose(g[5, 5, 3], 0.75) and np.all(g[..., :3] <= g[..., 3:] + 1e-6)  # two glows stack
    d.stroke("glow", [(10, 90), (90, 90)], (1, 1, 0), 10, mode="add")
    assert d.composite().max() <= 1.0


def test_setup_ops_join_the_next_batch():
    d = Doc.new(60, 40)
    d.add_layer("ink")
    d.mask_polygon("m", [(0, 0), (30, 0), (30, 30)])
    with d.batch("first strokes"):
        d.stroke("ink", [(1, 1), (20, 20)], (0, 0, 0), 4, mask="m")
    assert [e["label"] for e in d.history()] == ["first strokes"]
    d.add_layer("top")
    assert [e["label"] for e in d.history()] == ["first strokes", "setup"]
