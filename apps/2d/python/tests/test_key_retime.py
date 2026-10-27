"""key.scale, key.paste, layer.stagger and K (key.add fields "pose"): each is one undo step and lands at the right
times; the stagger orders are stable; a spring written as bounce / speed is the old spring at the defaults."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.keys import springs

from rostrum2d import KIND, ops_timing
from rostrum2d.ops_stagger import ranks

SAM = Who.person("sam")


@pytest.fixture
def doc(monkeypatch):
    monkeypatch.setattr(ops_timing, "times", lambda: {})
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "fps": 30, "duration": 10}},
             *[{"op": "layer.add", "target": "film", "args": {"type": "shape", "id": i}} for i in ("a", "b", "c")],
             {"op": "shape.set", "target": "b", "args": {"x": 100}},
             {"op": "key.add", "target": "a", "args": {"prop": "opacity", "t": 1.0, "v": 0}},
             {"op": "key.add", "target": "a", "args": {"prop": "opacity", "t": 2.0, "v": 1, "ease": "linear"}}], SAM)
    return d


def _ts(d, owner, prop="opacity"):
    return sorted(k["t"] for k in d.item(owner).get("keys", []) if k["prop"] == prop)


def test_scale_stretches_around_and_undoes_in_one(doc):
    doc.apply({"op": "key.scale", "target": ["a.opacity.k1000", "a.opacity.k2000"], "args": {"around": 1.0, "by": 2}}, SAM)
    assert _ts(doc, "a") == [1.0, 3.0]
    doc.undo(SAM)
    assert _ts(doc, "a") == [1.0, 2.0]


def test_paste_keeps_spacing_values_and_ease(doc):
    doc.apply({"op": "key.paste", "target": ["b", "c"], "args": {"from": ["a.opacity.k1000", "a.opacity.k2000"], "at": 4.0}}, SAM)
    for o in ("b", "c"):
        keys = sorted((k for k in doc.item(o)["keys"]), key=lambda k: k["t"])
        assert [(k["t"], k["v"]) for k in keys] == [(4.0, 0), (5.0, 1)] and keys[1]["ease"] == "linear"
    doc.undo(SAM)
    assert not doc.item("b").get("keys") and not doc.item("c").get("keys")


def test_pose_keys_every_layer_once(doc):
    doc.apply([{"op": "key.add", "target": [i], "args": {"fields": "pose", "t": 0.5}} for i in ("b", "c")], SAM, label="K")
    assert sorted({k["prop"] for k in doc.item("b")["keys"]}) == ["opacity", "rotation", "scale", "x", "y"]
    assert next(k["v"] for k in doc.item("b")["keys"] if k["prop"] == "x") == 100
    doc.undo(SAM)
    assert not doc.item("b").get("keys")


def test_stagger_spreads_from_the_earliest_and_undoes(doc):
    doc.apply({"op": "layer.stagger", "target": ["a", "b", "c"], "args": {"by": 0.5, "order": "picked"}}, SAM)
    assert [doc.item(i).get("start", 0.0) for i in "abc"] == [0.0, 0.5, 1.0]
    assert _ts(doc, "a") == [1.0, 2.0]                                  # the first doesn't move
    doc.undo(SAM)
    assert [doc.item(i).get("start", 0.0) for i in "abc"] == [0.0, 0.0, 0.0]
    for by in (0.5, 0.2):                                               # again: re-spread from the first
        doc.apply({"op": "layer.stagger", "target": ["a", "b", "c"], "args": {"by": by, "order": "picked"}}, SAM)
    assert [doc.item(i).get("start", 0.0) for i in "abc"] == [0.0, 0.2, 0.4]


def test_stagger_orders():
    items = [{"id": "l", "x": 0, "y": 50}, {"id": "m", "x": 50, "y": 0}, {"id": "r", "x": 100, "y": 50}]
    assert ranks(items, "left_to_right", []) == [0, 1, 2]
    assert ranks(items, "top_to_bottom", []) == [1, 0, 1]                        # a row starts together
    column = [{"id": "a", "x": 100, "y": 0}, {"id": "b", "x": 100.4, "y": 80}, {"id": "c", "x": 0, "y": 40}, {"id": "d", "x": 200, "y": 0}]
    assert ranks(column, "left_to_right", []) == [1, 1, 0, 2]                    # a column (within a pixel) starts together
    assert ranks(items, "stack", ["r", "m", "l"]) == [2, 1, 0]
    assert ranks(items, "centre", [])[0] == ranks(items, "centre", [])[2]        # equal distance: together
    assert ranks(items, "random", []) == ranks(list(reversed(items)), "random", [])[::-1]   # stable


def test_spring_words_match_the_old_numbers():
    assert springs.physics(springs.BOUNCE, springs.SPEED) == pytest.approx((170.0, 12.0), rel=1e-3)
    assert springs.feel(*springs.physics(0.2, 0.8)) == pytest.approx((0.2, 0.8), abs=1e-3)


def test_key_stagger_moves_each_layers_picked_keys_in_one_change(doc):
    for o in ("b", "c"):
        doc.apply({"op": "key.paste", "target": [o], "args": {"from": ["a.opacity.k1000", "a.opacity.k2000"], "at": 1.0}}, SAM)
    ids = [k["id"] for o in ("a", "b", "c") for k in doc.item(o)["keys"]]
    doc.apply({"op": "key.stagger", "target": ids, "args": {"by": 0.5, "order": "picked"}}, SAM)
    assert [_ts(doc, o) for o in ("a", "b", "c")] == [[1.0, 2.0], [1.5, 2.5], [2.0, 3.0]]
    doc.undo(SAM)
    assert [_ts(doc, o) for o in ("a", "b", "c")] == [[1.0, 2.0]] * 3


def test_after_the_last_key_reaches_the_engine_as_the_value_python_reads(doc):
    """Preview = export: the scene sent to the engine carries the written-out keys, and Python reads the same value."""
    from rostrum2d.evaluate import value_at
    from rostrum2d.scene import describe
    from rostrum_core.keys import track_value
    doc.apply({"op": "key.set", "target": ["a.opacity.k2000"], "args": {"after": "pingpong"}}, SAM)
    sent = next(n for n in describe(doc.data)["comp"]["layers"] if n["id"] == "a")["anim"]["opacity"]
    assert all("after" not in k for k in sent) and sent[-1]["t"] >= 10.0
    for t in (2.5, 3.25, 4.0, 6.6):
        assert abs(track_value(sent, t) - value_at(doc.item("a"), "opacity", t)) < 1e-9
    v = lambda t: value_at(doc.item("a"), "opacity", t)  # noqa: E731
    assert v(2.5) == pytest.approx(v(1.5)) and v(3.0) == 0 and v(4.5) == pytest.approx(v(1.5))       # back, then forth


def test_spring_bounce_speed_are_key_fields_and_script_tuple_round_trips(doc):
    from rostrum_core.errors import RostrumError
    from rostrum2d.script import run_source
    doc.apply({"op": "key.add", "target": "a", "args": {"prop": "x", "t": 1.0, "v": 5, "ease": "spring", "bounce": 0.3, "speed": 0.4}}, SAM)
    k = doc.item("a.x.k1000")
    assert (k["bounce"], k["speed"]) == (0.3, 0.4)
    for bad in ({"ease": "spring", "bounce": 2}, {"bounce": 0.3}):          # out of range; bounce on a smooth key
        with pytest.raises(RostrumError):
            doc.apply({"op": "key.add", "target": "a", "args": {"prop": "x", "t": 2.0, "v": 5, **bad}}, SAM)
    tree = run_source('comp("c", duration=2)\nshape("s").key("x", {0: 0, 1: (9, "spring", {"bounce": 0.3, "speed": 0.4})})', "t.py")
    key = tree["comps"][0]["layers"][1]["keys"][1]
    assert (key["ease"], key["bounce"], key["speed"]) == ("spring", 0.3, 0.4)
