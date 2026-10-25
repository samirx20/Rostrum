"""Chord ▾ operations (sound-pro-workflows SPEC § 3.9–3.11) and the Fit to key tie: what would break silently. A chord in
the key is the key's own; one undo removes only the added tones; strum keeps every end and is one step; an arpeggio
stays inside its chord and repeats with its seed; a note halfway between two notes of the key fits up."""
import pytest
from rostrum_core import Document, Who

from rostrum_sound import KIND

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def _doc(*calls):
    d = Document.new(KIND)
    d.apply([_op("doc.set", ["root"], tempo=120), _op("track.add", [], id="t", instrument="builtIn", builtIn="piano"),
             *calls], P)
    return d


def _pitches(d):
    return sorted(n["pitch"] for n in d.item("t")["notes"])


def test_chord_in_key_is_the_keys_own_and_one_undo_removes_only_the_added_tones():
    d = _doc(_op("key.add", [], at=0, key="C major"),
             _op("note.add", ["t"], id="d", pitch="D4", at={"beat": 0}, dur={"beats": 1}),
             _op("note.add", ["t"], id="b", pitch="B3", at={"beat": 4}, dur={"beats": 1}))
    d.apply(_op("note.chord", ["d", "b"], shape="key"), P)
    at = lambda beat: sorted((n["pitch"] for n in d.item("t")["notes"] if n["at"] == {"beat": beat}),  # noqa: E731
                             key=lambda p: (p[-1], "CDEFGAB".index(p[0])))
    assert at(0) == ["D4", "F4", "A4"] and at(4) == ["B3", "D4", "F4"]
    assert all(n["dur"] == {"beats": 1} for n in d.item("t")["notes"])
    d.undo(P)
    assert _pitches(d) == ["B3", "D4"]


def test_strum_keeps_every_end_spaces_the_starts_and_is_one_undo_step():
    d = _doc(*[_op("note.add", ["t"], id=i, pitch=p, at=1.0, dur=0.5, vel=0.8) for i, p in (("c", "C4"), ("e", "E4"), ("g", "G4"))])
    d.apply(_op("note.strum", ["c", "e", "g"], gap=40), P)
    got = {i: (d.item(i)["at"], d.item(i)["at"] + d.item(i)["dur"]) for i in "ceg"}
    assert [got[i][0] for i in "ceg"] == pytest.approx([1.0, 1.04, 1.08])
    assert all(end == pytest.approx(1.5) for _, end in got.values())
    d.apply(_op("note.strum", ["c", "e", "g"], gap=-20), P)              # again: re-spaced from the earliest start
    assert [d.item(i)["at"] for i in "gec"] == pytest.approx([1.0, 1.02, 1.04])
    d.undo(P)
    d.undo(P)
    assert [d.item(i)["at"] for i in "ceg"] == [1.0, 1.0, 1.0] and d.item("g")["dur"] == 0.5


def test_arpeggio_stays_inside_the_chord_and_repeats_with_its_seed():
    def run(seed):
        d = _doc(*[_op("note.add", ["t"], id=i, pitch=p, at={"beat": 2}, dur={"beats": 2}) for i, p in (("c", "C4"), ("e", "E4"), ("g", "G4"))])
        d.apply(_op("note.arpeggiate", ["c", "e", "g"], rate=0.25, mode="random", octaves=2, seed=seed), P)
        return [(n["pitch"], n["at"]["beat"], n["dur"]["beats"]) for n in sorted(d.item("t")["notes"], key=lambda n: n["at"]["beat"])]
    a = run(7)
    assert len(a) == 8 and all(2 - 1e-6 <= at and at + dur <= 4 + 1e-3 for _, at, dur in a)
    assert a == run(7)
    assert {p for p, _, _ in a} <= {"C4", "E4", "G4", "C5", "E5", "G5"}


def test_fit_to_key_nearest_goes_up_from_halfway():
    d = _doc(_op("key.add", [], at=0, key="D minor"), _op("note.add", ["t"], id="x", pitch="C#4", at=0, dur=1))
    d.apply(_op("note.fit_key", ["x"]), P)
    assert d.item("x")["pitch"] == "D4"
