"""A track's sound, the effect order and the track order: what people and agents rely on and would break silently.
Changing a sound keeps the notes and settings, the name follows only while it is the sound's own, and one undo puts
everything back; effects and tracks move in one step."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum_sound import KIND

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def _doc():
    d = Document.new(KIND)
    d.apply([_op("track.add", [], id="a", name="Felt piano", instrument="builtIn", builtIn="feltPiano"),
             _op("track.add", [], id="b", name="Lead", instrument="builtIn", builtIn="feltPiano"),
             _op("track.add", [], id="k", name="Drums", instrument="kit", kit="synth"),
             _op("note.add", ["a"], id="n", pitch="C4", at=0, dur=1),
             _op("hit.add", ["k"], id="h", drum="kick", at=0)], P)
    return d


def test_sound_changes_keep_the_notes_and_the_name_follows_unless_renamed():
    d = _doc()
    d.apply(_op("track.set", ["a", "b"], sound="synth"), P)
    assert (d.item("a")["instrument"], d.item("a")["name"], d.item("a")["notes"][0]["id"]) == ("synth", "Synth", "n")
    assert (d.item("b")["instrument"], d.item("b")["name"]) == ("synth", "Lead")      # the person's name stays
    d.undo(P)
    assert d.item("a")["builtIn"] == "feltPiano" and d.item("a")["name"] == "Felt piano"      # one step back


def test_a_sound_the_content_cannot_use_is_refused_in_words():
    d = _doc()
    with pytest.raises(RostrumError) as e:
        d.apply(_op("track.set", ["k"], sound="builtIn:warmPad"), P)       # hits need the drum kit
    assert "hits" in str(e.value)


def test_effects_and_tracks_move_in_one_step():
    d = _doc()
    for e in ("eq", "delay", "reverb"):
        d.apply(_op("effect.add", ["a"], effect=e), P)
    d.apply(_op("effect.move", ["a.reverb_1"], to=0), P)
    assert [e["effect"] for e in d.item("a")["effects"]] == ["reverb", "eq", "delay"]
    d.undo(P)
    assert [e["effect"] for e in d.item("a")["effects"]] == ["eq", "delay", "reverb"]
    d.apply(_op("track.move", ["k"], after="top"), P)
    assert [t["id"] for t in d.data["tracks"]] == ["k", "a", "b"]
