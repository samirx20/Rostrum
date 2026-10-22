"""Dragging a track into or out of a group (bus.add_track / bus.remove_track): one undo step, and the track keeps
every setting it had."""
from rostrum_core import Document, Who

from rostrum_sound import KIND

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def test_into_and_out_of_a_group_is_one_step_and_keeps_settings():
    d = Document.new(KIND)
    d.apply([_op("track.add", [], id="a", volume=0.4, pan=-0.3), _op("track.add", [], id="b"), _op("bus.add", [], id="g")], P)
    d.apply(_op("bus.add_track", ["g"], tracks=["a", "b"]), P)
    assert d.item("a")["output"] == "g" == d.item("b")["output"]
    assert d.item("a")["volume"] == 0.4 and d.item("a")["pan"] == -0.3
    d.apply(_op("bus.remove_track", ["g"], tracks=["a"]), P)
    assert d.item("a")["output"] == "master" and d.item("b")["output"] == "g"
    d.undo(P)
    assert d.item("a")["output"] == "g"                              # one undo brings it back in
