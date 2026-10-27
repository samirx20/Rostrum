"""Delete time / insert time across the whole song: a remove then an insert of the same stretch brings what was
outside it back to its time, and undo puts everything back (what agents rely on when they rearrange a song)."""
from rostrum_core import Document, Who

import pytest

from rostrum_sound import KIND
from rostrum_sound.doc import times

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def _song():
    d = Document.new(KIND)
    d.apply([_op("track.add", [], id="t", instrument="builtIn", builtIn="warmPad"), _op("track.add", [], id="u", instrument="builtIn", builtIn="warmPad"),
             _op("note.add", ["t"], id="a", pitch="C4", at=1, dur=1),
             _op("note.add", ["t"], id="in", pitch="C4", at=5, dur=1),
             _op("note.add", ["t"], id="long", pitch="C4", at=3, dur=4),
             _op("note.add", ["u"], id="b", pitch="C4", at={"beat": 20}, dur=1),
             _op("marker.add", [], name="drop", at=9),
             _op("note.add", ["u"], id="c", pitch="C4", at="#drop+0.5", dur=1),
             _op("tempo.add", [], at=8, bpm=90),
             _op("section.add", [], name="verse", at=2, end=12)], P)       # seconds: kept as the beat they fall on
    return d


def _end(d):
    return times.seconds(d.item("section.verse")["end"], d.data, "section.verse")


def _times(d):
    return {i: d.item(i)["at"] for i in ("a", "b", "c", "marker.drop", "section.verse")}


def test_remove_then_insert_brings_times_back_and_undo_restores_all():
    d = _song()
    before = {"times": _times(d), "doc": str(d.data)}
    d.apply(_op("range.remove", [], at=4, end=6), P)
    assert "in" not in [n["id"] for n in d.data["tracks"][0]["notes"]] and d.item("long")["dur"] == 2   # inside went; long note lost the range
    assert d.item("a")["at"] == 1 and _end(d) == pytest.approx(10)
    d.apply(_op("range.insert", [], at=4, length=2), P)
    assert _times(d)["a"] == before["times"]["a"] and _times(d)["marker.drop"] == before["times"]["marker.drop"]
    assert _end(d) == pytest.approx(12) and d.item("b")["at"] == before["times"]["b"]
    d.undo(P)
    d.undo(P)
    assert str(d.data) == before["doc"]
