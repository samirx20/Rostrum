"""Framing and cuts (ops_frame_fit.py, spec test 5): Move the frame to these ends with every layer inside the export at that time,
depth included; a cut holds the place one frame before; a cut on a marker moves with the marker."""
import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, ops_frame_fit, retime
from rostrum2d.boxes import corners
from rostrum2d.evaluate import value_at
from rostrum2d.frame import view

SAM = Who.person("sam")


def scene() -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "far"}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "near"}},
             {"op": "shape.set", "target": "far", "args": {"x": 3600, "y": 300, "w": 500, "h": 300, "depth": 3}},
             {"op": "shape.set", "target": "near", "args": {"x": 3000, "y": 800, "w": 200, "h": 200, "depth": -0.5}}], SAM)
    return d


def shown_corners(d, t):
    comp = d.item("film")
    cam = view.shot(comp, t)
    out = []
    for i in ("far", "near"):
        layer = d.item(i)
        m = view.layer_matrix(comp, cam, {"depth": layer["depth"]})
        out += [(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]) for x, y in corners(layer, t)]
    return out


def test_frame_these_puts_depth_layers_inside_the_export_with_room():
    d = scene()
    d.apply({"op": "frame.fit", "target": "frame", "args": {"to": "items", "ids": ["far", "near"], "at": 3}}, SAM)
    pts = shown_corners(d, 3)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    assert min(xs) >= 96 - 0.5 and max(xs) <= 1824 + 0.5 and min(ys) >= 54 - 0.5 and max(ys) <= 1026 + 0.5
    assert min(xs) == pytest.approx(96, abs=1) or min(ys) == pytest.approx(54, abs=1)   # as close as the room allows
    frame = d.item("frame")
    assert value_at(frame, "x", 0) == 960 and value_at(frame, "zoom", 0) == 1      # keyed at 0 s where it was
    assert {k["t"] for k in frame["keys"]} == {0.0, 3}
    d.undo(SAM)
    assert d.item("frame")["keys"] == []                                           # one undo step


def test_a_cut_holds_one_frame_before_and_follows_its_marker(monkeypatch):
    marks = {"logo lands": 2.4}
    monkeypatch.setattr(ops_frame_fit, "_times", lambda ctx: marks)
    d = scene()
    d.apply({"op": "frame.cut", "target": "frame", "args": {"at": "#logo lands", "to": "rect", "rect": [3200, 0, 1920, 1080]}}, SAM)
    keys = {(k["prop"], k["t"]): k for k in d.item("frame")["keys"]}
    fps = d.item("film").get("fps", 30)
    before = f"#logo lands-{round(1 / fps, 6):g}"
    assert keys[("x", before)]["ease"] == "hold" and keys[("x", before)]["v"] == 960
    assert keys[("x", "#logo lands")]["v"] == 4160

    def x_at(t):
        comp = retime.timed(d.item("film"), marks, fps)
        return value_at(view.of(comp), "x", t)
    assert x_at(2.35) == 960 and x_at(2.4) == 4160
    marks["logo lands"] = 4.0                                                      # the marker moves: the cut moves
    assert x_at(2.4) == 960 and x_at(3.9) == 960 and x_at(4.0) == 4160


def test_framing_a_view_the_frame_already_shows_holds_it_there():
    """2D final critic F2-2: a fit where the frame already is, after 0 s, keys its place there (and at 0 s): the next
    fit's move starts there, not from 0 s. At 0 s on a still frame nothing changes. Frame home at home holds too (F4-1)."""
    d = scene()
    d.apply({"op": "frame.fit", "target": "frame", "args": {"to": "view", "rect": [0, 0, 1920, 1080], "at": 0}}, SAM)
    assert not d.item("frame").get("keys")
    d.apply({"op": "frame.fit", "target": "frame", "args": {"to": "view", "rect": [0, 0, 1920, 1080], "at": 2}}, SAM)
    keys = sorted((k["prop"], k["t"], k["v"]) for k in d.item("frame")["keys"])
    assert keys == [("x", 0.0, 960.0), ("x", 2, 960.0), ("y", 0.0, 540.0), ("y", 2, 540.0), ("zoom", 0.0, 1.0), ("zoom", 2, 1.0)]
    d.apply({"op": "frame.home", "target": "frame", "args": {"at": 4}}, SAM)          # home already: a hold, no refusal
    assert {k["t"] for k in d.item("frame")["keys"] if k["prop"] == "zoom"} == {0.0, 2, 4}


def test_a_script_fits_in_time_order_with_an_eased_move():
    """FRICTION A2-2 / A3-4: a fit where the frame already is (0 s at home) is a no-op, a repeat on an animated frame
    holds there, and `ease` shapes the move into the next framing."""
    from rostrum2d import run_source
    src = ('comp("c", duration=6)\nshape("box", x=3000, y=500, w=400, h=300)\nf = frame()\n'
           'f.fit(rect=(0, 0, 1920, 1080), at=0)\nf.fit(rect=(0, 0, 960, 540), at=1)\n'
           'f.fit(rect=(0, 0, 960, 540), at=2)\nf.fit(["box"], at=5, ease="easeInOut")\n')
    d = Document.new(KIND)
    d.run_script("s.py", run_source(src, "s.py"))
    xs = sorted((k["t"], k["v"], k["ease"]) for k in d.item("frame")["keys"] if k["prop"] == "x")
    assert [t for t, _, _ in xs] == [0.0, 1, 2, 5]
    assert xs[1][1] == xs[2][1] and xs[2][2] == "easeInOut"          # held 1 s to 2 s, then the eased move to 5 s
    assert value_at(d.item("frame"), "x", 1.5) == xs[1][1]


def test_the_cameras_tools_write_no_keys_that_do_nothing():
    """A cut or Frame home keys only what changes (x, y, zoom); a turn nobody asked for is never keyed, so Problems has
    nothing to blame on the person (and never names `frame.rotation`)."""
    from rostrum2d import diagnose
    d = scene()
    d.apply({"op": "frame.cut", "target": "frame", "args": {"at": 2, "to": "rect", "rect": [3200, 0, 1920, 1080]}}, SAM)
    d.apply({"op": "frame.cut", "target": "frame", "args": {"at": 4}}, SAM)
    d.apply({"op": "frame.home", "target": "frame", "args": {"at": 5}}, SAM)
    assert {k["prop"] for k in d.item("frame")["keys"]} == {"x", "y", "zoom"}
    assert not [p for p in diagnose.problems(d.item("film")) if p["kind"] == "unused-keys"]
    # a field that does hold one value is still said in words (the layer's name, the field's label), never `frame.rotation`
    d.apply({"op": "key.add", "target": "far", "args": {"prop": "opacity", "t": 0, "v": 1}}, SAM)
    d.apply({"op": "key.add", "target": "far", "args": {"prop": "opacity", "t": 1, "v": 1}}, SAM)
    said = [p["message"] for p in diagnose.problems(d.item("film")) if p["kind"] == "unused-keys"]
    assert said and "far.opacity" not in said[0] and "opacity" in said[0]
