"""Pin to frame, Set depth and a new size (ops_depth.py, frame/make.py resized): a layer stays exactly where it shows in
the export at the playhead, and a pinned title keeps its distance from the frame's centre when the size changes. These
break silently otherwise (the picture jumps)."""
import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND
from rostrum2d.evaluate import value_at
from rostrum2d.frame import view

SAM = Who.person("sam")
T = 2.0


def scene() -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "title"}},
             {"op": "shape.set", "target": "title", "args": {"x": 1300, "y": 400, "w": 300, "h": 100, "depth": 2,
                                                              "rotation": 10, "anchorX": 0.2}},
             {"op": "key.add", "target": "title", "args": {"prop": "x", "t": 0, "v": 1200}},
             {"op": "key.add", "target": "title", "args": {"prop": "x", "t": 4, "v": 1500}},
             {"op": "key.add", "target": "frame", "args": {"prop": "x", "t": 0, "v": 960}},
             {"op": "key.add", "target": "frame", "args": {"prop": "x", "t": 4, "v": 1800}},
             {"op": "value.set", "target": "frame", "args": {"prop": "zoom", "v": 1.6}},
             {"op": "value.set", "target": "frame", "args": {"prop": "rotation", "v": 12}}], SAM)
    return d


def shown(d, lid="title", t=T):
    """(the export point of the layer's anchor, its shown scale, its shown turn) at t."""
    comp, layer = d.item("film"), d.item(lid)
    props = {f: value_at(layer, f, t) for f in ("x", "y", "scale", "rotation", "depth", "screenLock")}
    cam = view.shot(comp, t)
    m = view.layer_matrix(comp, cam, props)
    x, y = props["x"], props["y"]
    _, _, z, turn = view.parts(view.centre(comp), cam, props["depth"])
    k, r = (1.0, 0.0) if props["screenLock"] else (z, turn)
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5], props["scale"] * k, props["rotation"] + r


def test_pin_keeps_where_it_shows_and_unpin_round_trips():
    d = scene()
    before = shown(d)
    d.apply({"op": "layer.pin", "target": ["title"], "args": {"on": True, "keep": "shown", "at": T}}, SAM)
    assert d.item("title")["screenLock"] and shown(d) == pytest.approx(before, abs=1e-3)
    y_keys = [k for k in d.item("title")["keys"] if k["prop"] == "y"]
    assert [k["t"] for k in y_keys] == [0, 4]                  # turned with the frame: y keyed with x, the path kept
    d.apply({"op": "layer.pin", "target": ["title"], "args": {"on": False, "at": T}}, SAM)
    assert not d.item("title")["screenLock"] and shown(d) == pytest.approx(before, abs=1e-3)
    assert value_at(d.item("title"), "x", 0) == pytest.approx(1200, abs=1e-3)
    d.undo(SAM)
    d.undo(SAM)
    assert value_at(d.item("title"), "x", 4) == 1500 and not d.item("title").get("screenLock")   # one step each


def test_set_depth_keeps_the_shown_point_and_size():
    d = scene()
    d.apply({"op": "layer.set_depth", "target": ["title"], "args": {"depth": 0, "keep": "values"}}, SAM)
    before = shown(d)
    d.apply({"op": "layer.set_depth", "target": ["title"], "args": {"depth": 3, "keep": "shown", "at": T}}, SAM)
    assert d.item("title")["depth"] == 3 and shown(d) == pytest.approx(before, abs=1e-3)


def test_a_new_size_keeps_the_frame_and_a_pinned_title_its_distance_from_the_centre():
    d = scene()
    d.apply([{"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "logo"}},
             {"op": "shape.set", "target": "logo", "args": {"x": 960, "y": 540, "screenLock": True}},
             {"op": "key.add", "target": "logo", "args": {"prop": "y", "t": 1, "v": 600}}], SAM)
    frame = dict(d.item("frame"))
    d.apply({"op": "comp.size", "target": "film", "args": {"size": "vertical"}}, SAM)
    after = d.item("frame")
    assert {f: after[f] for f in ("zoom", "rotation", "homeX", "homeY")} == {f: frame[f] for f in ("zoom", "rotation", "homeX", "homeY")}
    assert after["keys"] == frame["keys"]
    logo = d.item("logo")
    assert logo["x"] == pytest.approx(540) and value_at(logo, "y", 1) == pytest.approx(1020)   # (1080-1920)/2, (1920-1080)/2
    assert value_at(d.item("title"), "x", 0) == 1200                                          # world layers stay
