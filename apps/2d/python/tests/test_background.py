"""Painted backgrounds: background.move keeps every stroke where it sits in the composition, and is one undo step."""
import copy

from rostrum_core import Document, Who

from rostrum2d import KIND, run_source
from rostrum2d import background as B

AGENT = Who.agent("tester")
SETUP = 'comp("c", fps=10, duration=2)\ncam = camera("cam")\ncam.key("x", {0: 700, 2: 1200})\n'


def test_move_keeps_every_stroke_in_place_and_is_one_undo_step():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SETUP, "s.py"))
    d.apply({"op": "background.add", "target": "c", "args": {"depths": [2.0, 0.5]}}, AGENT)
    far, near = (l for l in d.item("c")["layers"] if l["type"] == "drawing")
    paint = near["frames"][0]["paints"][0]["id"]
    d.apply([{"op": "stroke.add", "target": paint, "args": {"points": [[100 + 40 * i, 300], [400, 360 + i]], "size": 20}} for i in range(5)], AGENT)
    before = {s["id"]: [B.to_comp(d.item(near["id"]), *p[:2]) for p in s["points"]] for s in d.item(paint)["strokes"]}
    snapshot = copy.deepcopy(d.data)
    d.apply({"op": "background.move", "target": [paint], "args": {"into": far["id"]}}, AGENT)
    moved = {s["id"]: [B.to_comp(d.item(far["id"]), *p[:2]) for p in s["points"]] for s in d.item(paint)["strokes"]}
    assert moved.keys() == before.keys()
    assert all(abs(a - b) < 0.01 for k in before for p, q in zip(before[k], moved[k]) for a, b in zip(p, q))
    assert d.parent_of(paint)[0] == far["frames"][0]["id"]
    d.undo(AGENT)
    assert d.data == snapshot


def test_cover_the_frames_move_leaves_no_gap_for_a_turned_stretched_picture_and_a_drawing():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SETUP + 'cam.key("zoom", {0: 1, 2: 0.7})\ncam.key("rotation", {0: 0, 2: 12})\n', "s.py"))
    d.apply([{"op": "layer.add", "target": "c", "args": {"type": "shape", "id": "sky"}},
             {"op": "shape.set", "target": "sky", "args": {"x": 300, "y": 200, "w": 400, "h": 300, "rotation": 20,
                                                           "scaleX": 1.5, "anchorX": 0.2, "depth": 1.5}},
             {"op": "layer.add", "target": "c", "args": {"type": "drawing", "id": "hills"}},
             {"op": "drawing.set", "target": "hills", "args": {"w": 600, "h": 400, "rotation": 10, "scale": 1.3, "depth": 0.5}}], AGENT)
    assert B.gaps(d.item("c"), d.item("sky"))                  # small and off to one side: the frame sees past it
    d.apply({"op": "background.fit", "target": ["sky", "hills"], "args": {}}, AGENT)
    sky = d.item("sky")
    assert B.gaps(d.item("c"), sky) == [] and sky["rotation"] == 20 and sky["scaleX"] == 1.5
    assert B.gaps(d.item("c"), d.item("hills")) == [] and d.item("hills")["rotation"] == 10      # the canvas grew


def test_the_warning_bands_shortcut_never_skips_a_layer_that_covers_the_frame():
    from rostrum2d import cover
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SETUP + 'cam.key("zoom", {0: 1, 2: 1.6})\n', "s.py"))
    d.apply([{"op": "layer.add", "target": "c", "args": {"type": "shape", "id": "sky"}},
             {"op": "shape.set", "target": "sky", "args": {"w": 400, "h": 300}}], AGENT)
    c = d.item("c")
    assert cover.never_covers(c, d.item("sky"), B.shots(c))          # far too small: no walk through the piece
    d.apply({"op": "background.fit", "target": ["sky"], "args": {}}, AGENT)
    c = d.item("c")
    assert not cover.never_covers(c, d.item("sky"), B.shots(c))
    assert cover.report(c, d.item("sky"), B.shots(c), 10.0)[1]       # it covers: the band is worked out


def test_a_bar_growing_through_the_frame_is_not_a_backdrop():
    """Production round: a bar whose own size animates past the frame and back got warning stripes over the art."""
    from rostrum2d import cover
    d = Document.new(KIND)
    d.run_script("s.py", run_source('comp("c", fps=10, duration=2)\n', "s.py"))
    d.apply([{"op": "layer.add", "target": "c", "args": {"type": "shape", "id": "bar"}},
             {"op": "shape.set", "target": "bar", "args": {"x": 960, "y": 540, "w": 40, "h": 10}}], AGENT)
    for t, w, h in ((0, 40, 10), (1, 4000, 3000), (2, 40, 10)):
        d.apply([{"op": "key.add", "target": ["bar"], "args": {"prop": "w", "t": t, "v": w}},
                 {"op": "key.add", "target": ["bar"], "args": {"prop": "h", "t": t, "v": h}}], AGENT)
    c = d.item("c")
    assert not cover.report(c, d.item("bar"), B.shots(c), 10.0)[1]      # no band (cover_band shows edges only for a backdrop)
