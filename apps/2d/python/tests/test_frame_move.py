"""Drawings on the timeline (ops_draw.py): a new drawing without a frame lands one New-ones-hold after the last; moving
a drawing keeps its strokes and leaves the other drawings where they were, the list sorted; each is one undo step."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND

SAM = Who.person("sam")


def drawn() -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             {"op": "layer.add", "target": "film", "args": {"type": "drawing", "id": "fire"}},
             {"op": "drawing.set", "target": "fire", "args": {"w": 100, "h": 100, "eachFrame": True, "newHold": 2}}], SAM)
    d.apply({"op": "paint.stroke", "target": "fire", "args": {"points": [[10, 10], [90, 90]], "space": "canvas"}}, SAM)
    d.apply({"op": "frame.add", "target": "fire", "args": {"id": "f2"}}, SAM)
    d.apply({"op": "frame.add", "target": "fire", "args": {"id": "f3", "copy": "f2"}}, SAM)
    return d


def ats(d):
    return [(f["id"], f["at"]) for f in d.item("fire")["frames"]]


def test_new_ones_hold_and_move_keep_strokes_and_neighbours():
    d = drawn()
    first = d.item("fire")["frames"][0]["id"]
    assert ats(d) == [(first, 0), ("f2", 2), ("f3", 4)]
    strokes = d.item("fire")["frames"][0]["paints"][0]["strokes"]
    d.apply({"op": "frame.move", "target": first, "args": {"to": 6}}, SAM)
    assert ats(d) == [("f2", 2), ("f3", 4), (first, 6)]
    assert d.item("fire")["frames"][2]["paints"][0]["strokes"] == strokes
    with pytest.raises(RostrumError, match="already has a drawing"):
        d.apply({"op": "frame.move", "target": "f2", "args": {"to": 4}}, SAM)
    d.undo(SAM)
    assert ats(d) == [(first, 0), ("f2", 2), ("f3", 4)]
