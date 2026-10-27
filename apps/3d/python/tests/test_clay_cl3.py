"""CL3 clay making, what would break silently: a drawing's points survive the plane they are stored on; a new drawn
clay stands where it was drawn, turned so Mirror's X = 0 runs down its middle; a tiny drawing is a lump; a hidden
step leaves the core's chain; Turn into clay hides the original in one undo step, and the clay rebuilds when the
original changes."""
import math

import pytest
from rostrum_core import Document, Who

from rostrum3d import KIND
from rostrum3d.clay_scene import chain

SAM = Who.person()
BODY = [[-0.1, 0.0, 0.0], [0.1, 0.0, 0.0], [0.08, 0.3, 0.0], [-0.08, 0.3, 0.0]]


def _doc(**args):
    d = Document.new(KIND)
    d.apply({"op": "clay.add", "args": {"id": "c", **args}}, SAM)
    return d


def _back(step):
    """The stored plane + 2-D outline → 3-D points again."""
    p = step["plane"]
    o, u, v = p[:3], p[3:6], p[6:]
    return [[o[i] + a * u[i] + b * v[i] for i in range(3)] for a, b in step["outline"]]


def test_a_drawing_round_trips_through_its_plane():
    d = _doc(at=[0, 0, 0], radius=0.2)
    t = math.radians(30)                                     # a tilted plane, in the clay's own space
    pts = [[x * math.cos(t), y, 0.05 + x * math.sin(t)] for x, y in ((-.1, -.1), (.1, -.1), (.12, .1), (-.1, .12))]
    d.apply({"op": "clay.draw", "target": ["c"], "args": {"outline": pts, "name": "arm"}}, SAM)
    step = d.item("c")["steps"][-1]
    assert step["shape"] == "outline" and step["name"] == "arm" and step["puff"] == 1.0
    assert [x for p in _back(step) for x in p] == pytest.approx([x for p in pts for x in p], abs=1e-5)
    assert abs(step["plane"][4]) < 1e-9                       # u lies flat: the plane's most horizontal direction
    assert 0 < step["blend"] <= 0.05


def test_a_new_drawn_clay_stands_where_it_was_drawn_turned_along_it():
    side = [[0.5, 0.2 + y, 1.0 + z] for z, y in ((0, 0), (0.4, 0), (0.35, 0.3), (0.05, 0.3))]   # drawn facing +X
    d = _doc(draw=side, facing=[1, 0, 0])
    c = d.item("c")
    assert (c["x"], c["y"], c["z"]) == pytest.approx((0.5, 0.2, 1.2))   # horizontal middle, lowest point
    assert c["ry"] == pytest.approx(90.0)                               # its X along the drawing (scene −Z)
    step = c["steps"][0]
    assert step["plane"][3:6] == pytest.approx([1, 0, 0], abs=1e-9)     # u = the clay's X: Mirror's X = 0 its middle
    t = math.radians(c["ry"])
    world = [[c["x"] + x * math.cos(t) + z * math.sin(t), c["y"] + y, c["z"] - x * math.sin(t) + z * math.cos(t)]
             for x, y, z in _back(step)]
    assert [x for p in world for x in p] == pytest.approx([x for p in side for x in p], abs=1e-5)


def test_a_tiny_drawing_is_a_lump():
    d = _doc(at=[0, 0, 0], radius=0.2)
    d.apply({"op": "clay.set", "target": ["c"], "args": {"brushSize": 0.02}}, SAM)
    scribble = [[0, 0.2, 0], [0.002, 0.2, 0], [0.002, 0.201, 0], [0, 0.201, 0]]       # thinner than 1.5 grains
    d.apply({"op": "clay.draw", "target": ["c"], "args": {"outline": scribble}}, SAM)
    d.apply({"op": "clay.draw", "target": ["c"], "args": {"outline": BODY[:3]}}, SAM)  # under 4 points
    for step in d.item("c")["steps"][-2:]:
        assert step["shape"] == "sphere" and step["radius"] == 0.02
    assert d.item("c")["steps"][-2]["at"] == pytest.approx([0.001, 0.2005, 0])


def test_a_hidden_step_leaves_the_chain():
    d = _doc(draw=BODY, facing=[0, 0, 1])
    d.apply({"op": "clay.lump", "target": ["c"], "args": {"at": [0, 0.3, 0], "radius": 0.05}}, SAM)
    d.apply({"op": "clay.spin", "target": ["c"], "args": {"profile": [[0, .3, 0], [.05, .3, 0], [0, .4, 0]]}}, SAM)
    steps = d.item("c")["steps"]
    full = chain(steps)
    d.apply({"op": "claystep.set", "target": [steps[1]["id"]], "args": {"hidden": True}}, SAM)
    hidden = chain(d.item("c")["steps"])
    assert len(hidden) == 2 and hidden[0]["key"] == full[0]["key"]
    assert hidden[1]["key"] == chain([steps[0], steps[2]])[1]["key"] != full[2]["key"]
    assert hidden[1]["shape"] == "spin"


def test_turn_into_clay_hides_the_original_in_one_undo_step_and_follows_it():
    d = Document.new(KIND)
    d.apply({"op": "mesh.add", "args": {"id": "box", "name": "Box", "shape": "box", "x": 0.3}}, SAM)
    before = d.data
    d.apply({"op": "clay.from_item", "target": ["box"], "args": {}}, SAM)
    clay = next(i for i in d.data["items"] if i["type"] == "clay")
    assert clay["name"] == "Box clay" and clay["x"] == 0.3 and clay["symmetry"] == "off"
    assert clay["steps"][0]["shape"] == "item" and clay["steps"][0]["source"] == "box"
    assert d.item("box")["visible"] is False
    key = chain(clay["steps"], d.data)[0]["key"]
    d.apply({"op": "mesh.set", "target": ["box"], "args": {"width": 0.5}}, SAM)
    wider = chain(clay["steps"], d.data)[0]["key"]
    assert wider != key                                            # the source changed: the clay rebuilds
    d.apply({"op": "mesh.set", "target": ["box"], "args": {"visible": True}}, SAM)
    assert chain(clay["steps"], d.data)[0]["key"] == wider         # showing it again changes no shape
    d.undo(SAM), d.undo(SAM), d.undo(SAM)
    assert d.data == before
