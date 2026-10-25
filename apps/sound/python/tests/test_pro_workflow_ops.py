"""The pro-workflow operations (sound-pro-workflows SPEC § 3.2–3.5): what would break silently. Repeat × N is one undo
step and never crosses its `until`; transpose by key steps reads each note's own key and fails whole past the 128 notes;
humanize with length repeats with the seed; track.feel merges (never wipes a person's feel); quantize swing moves only
the off-beat cells. (perform.person false with swing: the engine's contract/tests.rs.)"""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum_sound import KIND

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def _doc(*calls):
    d = Document.new(KIND)
    d.apply([_op("doc.set", ["root"], tempo=120), _op("track.add", [], id="t", instrument="builtIn", builtIn="piano"),
             *calls], P)
    return d


def _notes(d):
    return sorted(d.item("t")["notes"], key=lambda n: n["at"]["beat"])


def test_repeat_four_times_is_four_copies_in_one_undo_step():
    d = _doc(*[_op("note.add", ["t"], id=f"n{i}", pitch="C4", at={"beat": i}, dur={"beats": 1}) for i in range(4)])
    d.apply(_op("note.duplicate", [f"n{i}" for i in range(4)], times=4), P)
    assert [n["at"]["beat"] for n in _notes(d)] == pytest.approx(list(range(20)))
    d.undo(P)
    assert len(d.item("t")["notes"]) == 4


def test_until_cuts_the_last_copy_at_the_point_and_never_crosses_it():
    d = _doc(_op("note.add", ["t"], id="a", pitch="C4", at={"beat": 0}, dur={"beats": 3}),
             _op("section.add", [], name="verse", at=0, end=5))                    # 5 s = beat 10 at 120 bpm
    d.apply(_op("note.duplicate", ["a"], until={"section": "verse"}), P)
    got = [(n["at"]["beat"], n["dur"]["beats"]) for n in _notes(d)]
    assert got == [(0, 3), (3, 3), (6, 3), (9, 1)]                                # the last one cut at beat 10
    d2 = _doc(_op("note.add", ["t"], id="a", pitch="C4", at={"beat": 0}, dur={"beats": 3}),
              _op("marker.add", [], name="drop", at=4.5))
    d2.apply(_op("note.duplicate", ["a"], until="#drop", times=2), P)              # times caps the copies
    assert [n["at"]["beat"] for n in _notes(d2)] == [0, 3, 6]


def test_transpose_steps_uses_each_notes_key_and_fails_whole_past_the_128_notes():
    d = _doc(_op("key.add", [], at=0, key="C major"), _op("key.add", [], at=2, key="F major"),
             _op("note.add", ["t"], id="c", pitch="A4", at={"beat": 0}, dur=0.5),        # C major: A -> B
             _op("note.add", ["t"], id="f", pitch="A4", at={"beat": 4}, dur=0.5),        # F major: A -> Bb
             _op("note.add", ["t"], id="ch", pitch=["A4", "C5"], at={"beat": 1}, dur=0.5))
    d.apply(_op("note.transpose", ["c", "f", "ch"], steps=1), P)
    assert (d.item("c")["pitch"], d.item("f")["pitch"], d.item("ch")["pitch"]) == ("B4", "Bb4", ["B4", "D5"])
    d.apply(_op("note.add", ["t"], id="top", pitch=126, at={"beat": 2}, dur=0.5), P)
    before = {n["id"]: n["pitch"] for n in d.item("t")["notes"]}
    for args in ({"steps": 2}, {"semitones": 3}):
        with pytest.raises(RostrumError, match="128 notes"):
            d.apply(_op("note.transpose", ["c", "top"], **args), P)
        assert {n["id"]: n["pitch"] for n in d.item("t")["notes"]} == before        # nothing changed
    with pytest.raises(RostrumError, match="give exactly one"):
        d.apply(_op("note.transpose", ["c"], steps=1, semitones=1), P)
    with pytest.raises(RostrumError, match="has no key"):
        _doc(_op("note.add", ["t"], id="x", pitch="C4", at=0, dur=1)).apply(_op("note.transpose", ["x"], steps=1), P)


def test_humanize_with_length_is_the_same_every_run():
    def run(seed):
        d = _doc(*[_op("note.add", ["t"], id=f"n{i}", pitch="C4", at={"beat": i}, dur={"beats": 1}) for i in range(6)])
        d.apply(_op("note.humanize", [f"n{i}" for i in range(6)], timing=20, velocity=0.1, length=0.3, seed=seed), P)
        return [(n["at"], n["dur"], n["vel"]) for n in d.item("t")["notes"]]
    a = run(3)
    assert a == run(3)
    assert a != run(4)
    assert any(dur != {"beats": 1} for _, dur, _ in a)


def test_track_feel_merges_and_never_wipes_a_persons_feel():
    d = _doc(_op("track.set", ["t"], perform={"timing": 15, "accent": 0.1}))
    d.apply(_op("track.feel", ["t"], swing=0.5), P)
    assert d.item("t")["perform"] == {"timing": 15, "accent": 0.1, "swing": 0.5}
    d.apply(_op("track.feel", ["t"], accent=None, person=False), P)
    assert d.item("t")["perform"] == {"timing": 15, "swing": 0.5, "person": False}
    d.apply(_op("track.set", ["t"], perform=False), P)
    d.apply(_op("track.feel", ["t"], swing=0.3), P)
    assert d.item("t")["perform"] == {"person": False, "swing": 0.3}


def test_quantize_swing_moves_only_the_off_beat_cells():
    d = _doc(_op("track.add", [], id="k", instrument="kit", kit="drums"),
             *[_op("hit.add", ["k"], id=f"h{i}", drum="hat", at={"beat": b}) for i, b in enumerate([0.05, 0.55, 1.03, 1.45])])
    d.apply(_op("hit.quantize", [f"h{i}" for i in range(4)], grid=0.5, swing=1), P)
    got = [d.item(f"h{i}")["at"]["beat"] for i in range(4)]
    assert got == pytest.approx([0, 0.5 + 1 / 6, 1, 1.5 + 1 / 6], abs=1e-3)
