"""layer.shift and layer.trim (ops_timing.py): a move takes everything in the layer along and undoes in one step; tying a
layer to a marker lands its start on it; trimming a start onto a marker moves nothing that is seen."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, ops_timing, retime

SAM = Who.person("sam")


@pytest.fixture
def doc(monkeypatch):
    monkeypatch.setattr(ops_timing, "times", lambda: {"drop": 2.0})
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "fps": 30}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "dot"}},
             {"op": "shape.set", "target": "dot", "args": {"start": 1.0, "end": 3.0}},
             {"op": "key.add", "target": "dot", "args": {"prop": "opacity", "t": 1.5, "v": 1}},
             {"op": "key.add", "target": "dot", "args": {"prop": "opacity", "t": "#drop+0.2", "v": 0}}], SAM)
    return d


def _dot(d):
    return d.item("dot")


def _fixed(d):
    return [k["t"] for k in _dot(d)["keys"]]


def test_shift_moves_everything_and_undoes(doc):
    doc.apply({"op": "layer.shift", "target": "dot", "args": {"by": 0.5}}, SAM)
    dot = _dot(doc)
    assert (dot["start"], dot["end"]) == (1.5, 3.5) and sorted(map(str, _fixed(doc))) == ["#drop+0.2", "2.0"]
    doc.undo(SAM)
    assert (_dot(doc)["start"], _dot(doc)["end"]) == (1.0, 3.0)


def test_shift_to_a_marker_ties_and_lands_on_it(doc):
    doc.apply({"op": "layer.shift", "target": "dot", "args": {"to": "#drop"}}, SAM)
    dot = _dot(doc)
    assert dot["marker"] == "drop" and dot["start"] == 0 and dot["end"] == 2.0 and 0.5 in _fixed(doc)
    assert retime.timed(doc.data["comps"][0], {"drop": 2.0}, 30)["layers"][1]["start"] == 2.0
    with pytest.raises(RostrumError, match="nowhere"):
        doc.apply({"op": "layer.shift", "target": "dot", "args": {"to": "#nowhere"}}, SAM)


def test_trim_start_on_a_marker_keeps_what_is_seen(doc):
    seen = lambda: [k["t"] for k in retime.timed(doc.data["comps"][0], {"drop": 2.0}, 30)["layers"][1]["keys"]]
    before = seen()
    doc.apply({"op": "layer.trim", "target": "dot", "args": {"start": "#drop"}}, SAM)
    dot = _dot(doc)
    assert dot["marker"] == "drop" and dot["start"] == 0 and seen() == before
    with pytest.raises(RostrumError, match="before it starts"):
        doc.apply({"op": "layer.trim", "target": "dot", "args": {"end": 1.5}}, SAM)
