"""Select-then-act operations: what would break silently. Times keep their form (beats / marker / seconds), a
split then join gives the clip back, and "group tracks" is one undo step that routes."""
import numpy as np
import soundfile as sf
from rostrum_core import Document, Who

from rostrum_sound import KIND
from rostrum_sound.doc.select_time import inserted

P = Who.person()


def _doc(calls):
    d = Document.new(KIND)
    d.apply(calls, P)
    return d


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def test_quantize_move_keep_the_time_form():
    d = _doc([_op("track.add", [], id="t", builtIn="warmPad", instrument="builtIn"),
              _op("marker.add", [], name="drop", at=4),
              _op("note.add", ["t"], id="a", pitch="C4", at={"beat": 1.1}, dur=1),
              _op("note.add", ["t"], id="b", pitch="C4", at="#drop+0.13", dur=1),
              _op("note.add", ["t"], id="c", pitch="C4", at=2.13, dur=1)])
    d.apply(_op("note.quantize", ["a", "b", "c"], grid=0.5), P)
    assert d.item("a")["at"] == {"beat": 1.0}                        # beats stay beats
    assert d.item("b")["at"].startswith("#drop")                     # a marker time keeps its marker
    assert isinstance(d.item("c")["at"], float)
    d.apply(_op("note.move", ["a", "b", "c"], by={"beats": 2}), P)
    assert d.item("a")["at"] == {"beat": 3.0} and d.item("b")["at"].startswith("#drop")


def test_split_then_join_gives_the_clip_back(tmp_path):
    wav = tmp_path / "x.wav"
    sf.write(str(wav), np.random.default_rng(1).uniform(-.5, .5, 44100 * 2), 44100)
    d = _doc([_op("track.add", [], id="t"), _op("clip.add", ["t"], id="k", media=str(wav), at=1, length=2)])
    d.apply(_op("clip.split", ["k"], at=2.5), P)
    ids = [c["id"] for c in d.item("t")["clips"]]
    assert len(ids) == 2 and d.item(ids[1])["in"] == 1.5 and d.item(ids[1])["length"] == 0.5
    d.apply(_op("clip.join", ids), P)
    assert [c["id"] for c in d.item("t")["clips"]] == ["k"] and d.item("k")["length"] == 2.0


def test_group_tracks_is_one_undo_step():
    d = _doc([_op("track.add", [], id="a"), _op("track.add", [], id="b")])
    c = d.apply(_op("bus.from_tracks", ["a", "b"]), P)
    bus = inserted(c)[0]
    assert d.item("a")["output"] == bus == d.item("b")["output"]
    d.undo(P)
    assert not d.item("a")["output"] == bus and not d.item("root")["buses"]
