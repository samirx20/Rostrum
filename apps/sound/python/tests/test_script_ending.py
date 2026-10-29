"""ending(kind, at): every chosen part lands on `at`, nothing runs past it, the length (when the script set none) leaves room for the kind, the
home chord follows key(), and root["ending"] keeps what was asked (the ending check reads it). Wrong here is only heard."""
import pytest
from rostrum_core import RostrumError

from rostrum_sound import run_source
from rostrum_sound.doc import keys as K

BAND = """
tempo(60); key("{key}")
p = track("piano", builtIn="piano"); b = track("bass", builtIn="uprightBass"); d = track("drums", kit="drums")
for i in range(4):
    p.chord(["G3", "Bb3", "D4"], at=bar(i + 1), dur=beats(6), vel=0.6)     # rings across the next bar line
    b.note("G2", at=bar(i + 1), dur=beats(4))
    d.hit("kick", at=bar(i + 1))
p.note("E5", at=bar(5) + beats(1), dur=beats(1))                            # after the ending: dropped
{length}marker("end", at=bar(5))
{ending}
"""


def run(ending, key="D minor", length=""):
    return run_source(BAND.format(key=key, ending=ending, length=length), "song.py")


def _notes(tree, id_):
    return next(t for t in tree["tracks"] if t["id"] == id_)["notes"]


def _end_beat(n):
    d = n["dur"]
    return n["at"]["beat"] + d["beats"] if isinstance(d, dict) else None


def test_ring_lands_every_part_on_at_and_rings_past_it():
    tree = run('ending("ring", at="#end")')
    for id_ in ("piano", "bass"):
        notes = _notes(tree, id_)
        last = notes[-1]
        assert last["at"] == "#end" and last["dur"] >= 3.0                    # held, in seconds
        assert all(_end_beat(n) <= 16 for n in notes[:-1])                     # bar(5) is beat 16 at 4/4: nothing past it
    assert tree["length"] == pytest.approx(16 + _notes(tree, "piano")[-1]["dur"] + 1.0)   # at + the ring + its tail (60 bpm)
    assert tree["ringOut"] is True
    assert tree["ending"] == {"kind": "ring", "at": "#end", "at_s": 16.0, "home": "D minor"}


def test_a_length_the_script_set_stays():
    """Sam, 2026-10-29: a tool never moves what the writer set; the reply gives the arithmetic instead."""
    tree = run('ending("ring", at="#end")', length="length(bar(7)); ")
    assert tree["length"] == {"beat": 24.0} and tree["ringOut"] is True


def test_button_is_short_and_the_length_leaves_the_room_tail():
    tree = run('ending("button", at=bar(5))')
    last = _notes(tree, "piano")[-1]
    assert last["at"] == {"beat": 16} and last["dur"] <= 0.5
    assert 16 + 1.0 <= tree["length"] - last["dur"] <= 16 + 2.0              # the room tail (a crash's longest) inside the file
    hits = {(h["drum"], h["at"] if isinstance(h["at"], str) else h["at"]["beat"]) for h in
            next(t for t in tree["tracks"] if t["id"] == "drums")["hits"]}
    assert {("kick", 16), ("crash", 16)} <= hits


@pytest.mark.parametrize("key,pcs,root", [("D minor", {2, 5, 9}, 2), ("Eb major", {3, 7, 10}, 3)])
def test_the_last_chord_is_the_home_chord_of_the_key(key, pcs, root):
    tree = run('ending("ring", at="#end")', key)
    for id_ in ("piano", "bass"):
        assert {m % 12 for m in K.midis(_notes(tree, id_)[-1]["pitch"])} <= pcs
    assert K.midi(_notes(tree, "bass")[-1]["pitch"]) % 12 == root            # the lowest part on the root
    assert tree["ending"]["home"] == key


def test_fade_keeps_the_parts_and_writes_the_fall_ending_on_the_length():
    tree = run('ending("fade", at="#end", ring=4.0)')
    lane = tree["master"][0]["automation"][0]["points"]
    assert lane[0][0] == pytest.approx(12.0) and lane[-1][0] == pytest.approx(16.0) and lane[-1][1] < 0.05
    assert tree["length"] == pytest.approx(16.0) and tree["ending"]["kind"] == "fade"


@pytest.mark.parametrize("call", ['ending("big")', 'ending("ring", at="#nowhere")', 'ending("fade", chord="V")'])
def test_a_wrong_ending_is_refused_in_words(call):
    with pytest.raises(RostrumError):
        run(call)
