"""stroke.transform (paint_transform.py): strokes moved, scaled and turned by numbers, in composition px through the
element's place, in one undo step; the brush size follows the scale. The screen's handles record this same call."""
from rostrum_core import Document, Who

from rostrum2d import KIND

SAM = Who.person("sam")


def painted() -> Document:
    """A 200 × 100 shape at x 100..300, y 100..200 with one stroke along y 150 from x 150 to 250 (composition px)."""
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "width": 400, "height": 300, "duration": 1}},   # made at its size: its frame at home
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "egg"}},
             {"op": "shape.set", "target": "egg", "args": {"x": 200, "y": 150, "w": 200, "h": 100}}], SAM)
    d.apply({"op": "paint.stroke", "target": "egg", "args": {"points": [[150, 150], [250, 150]], "size": 10, "id": "s1"}}, SAM)
    return d


def test_turn_scale_move_is_one_step_in_composition_px():
    d = painted()
    before = d.item("s1")["points"]
    d.apply({"op": "stroke.transform", "target": ["s1"], "args": {"turn": 90, "scale": 0.5, "dx": 10}}, SAM)
    s = d.item("s1")
    # about the box centre (200, 150): half as long, standing up, 10 px right -> x 210, y 125..175 (canvas = comp - 100.5)
    assert [p[:2] for p in s["points"]] == [[109.5, 24.5], [109.5, 74.5]]
    assert s["size"] == 5
    d.undo(SAM)
    assert d.item("s1")["points"] == before and d.item("s1")["size"] == 10


def test_moving_strokes_past_a_drawings_edge_grows_it_and_loses_nothing():
    """Dragging picked paint past the edge cut it off for good (the drawing stayed its size); now the canvas grows, as
    painting past the edge does, and undo takes the move and the growth back together."""
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "width": 400, "height": 300, "duration": 1}},
             {"op": "layer.add", "target": "film", "args": {"type": "drawing", "id": "sky", "name": "sky"}},
             {"op": "drawing.set", "target": "sky", "args": {"w": 200, "h": 100}}], SAM)
    d.apply({"op": "paint.stroke", "target": "sky", "args": {"points": [[50, 40], [150, 60]], "size": 10, "id": "s1", "space": "canvas"}}, SAM)
    d.apply({"op": "stroke.transform", "target": ["s1"], "args": {"dx": -80, "space": "canvas"}}, SAM)     # left past x 0
    sky, s = d.item("sky"), d.item("s1")
    assert sky["w"] > 200 and all(0 <= p[0] <= sky["w"] and 0 <= p[1] <= sky["h"] for p in s["points"])
    assert s["points"][1][0] - s["points"][0][0] == 100                                                   # shape kept
    w_now = sky["w"]
    d.apply({"op": "stroke.transform", "target": ["s1"], "args": {"dx": 400, "space": "canvas"}}, SAM)    # right past the edge
    sky, s = d.item("sky"), d.item("s1")
    assert sky["w"] > w_now and max(p[0] for p in s["points"]) <= sky["w"]
    d.undo(SAM)
    assert d.item("sky")["w"] == w_now
