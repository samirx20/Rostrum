"""A range target (`{"track", "from", "to"}`) names exactly the notes starting in it, so an agent never parses ids; an
empty range is a loud error that says where the track's notes are (mcp/range_target.py)."""
import pytest

from rostrum_core import Document, RostrumError, Who
from rostrum_sound import KIND
from rostrum_sound.mcp import range_target

P = Who.person()


def test_a_range_selects_the_notes_starting_in_it_and_an_empty_one_fails():
    d = Document.new(KIND)
    d.apply([{"op": "track.add", "target": [], "args": {"id": "g", "instrument": "builtIn", "builtIn": "piano"}}] + [
        {"op": "note.add", "target": ["g"], "args": {"id": f"n{b}", "pitch": "C4", "at": {"beat": b}, "dur": {"beats": 1}}}
        for b in (0, 3, 4, 7, 8)], P)
    call = {"op": "note.transpose", "target": [{"track": "g", "from": {"bar": 1}, "to": {"bar": 2}}], "args": {"semitones": 1}}
    assert range_target.expand(d, KIND.registry, [call])[0]["target"] == ["n0", "n3"]         # 4/4: bar 2 starts on beat 4, not included
    call["target"] = [{"track": "g", "from": {"bar": 2}}]
    assert range_target.expand(d, KIND.registry, [call])[0]["target"] == ["n4", "n7", "n8"]
    call["target"] = [{"track": "g", "from": {"bar": 9}, "to": {"bar": 10}}]
    with pytest.raises(RostrumError, match="holds no notes"):
        range_target.expand(d, KIND.registry, [call])
