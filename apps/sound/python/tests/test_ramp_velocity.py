"""Ramp velocity sets each note by where it starts, between the first and the last, in one step: a crescendo drawn
wrong (a chord split, the last note missed) would only be heard."""
import pytest
from rostrum_core import Document, Who

from rostrum_sound import KIND, run_source
from rostrum_sound.mcp import range_target

SONG = """
tempo(60)
b = track("b", synth="saw")
for i in range(5):
    b.note("C4", at=beat(i), dur=beats(1), vel=0.6)
b.note("E4", at=beat(2), dur=beats(1), vel=0.6)
"""


def _doc():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"))
    return doc


def _vels(doc):
    return sorted((n["at"]["beat"] if isinstance(n["at"], dict) else n["at"], n["vel"]) for n in doc.item("b")["notes"])


def test_linear_ramp_by_time_and_chords_together():
    doc = _doc()
    ids = [n["id"] for n in doc.item("b")["notes"]]
    doc.apply({"op": "note.ramp_velocity", "target": ids, "args": {"start": 0.4, "end": 0.8}}, Who.person())
    assert [v for _, v in _vels(doc)] == [0.4, 0.5, 0.6, 0.6, 0.7, 0.8]      # the chord at beat 2: both 0.6


def test_ease_and_a_range_target():
    doc = _doc()
    call = {"op": "note.ramp_velocity", "target": [{"track": "b", "from": {"beat": 0}, "to": {"beat": 3.5}}],
            "args": {"start": 0.9, "end": 0.3, "curve": "ease"}}
    doc.apply(range_target.expand(doc, KIND.registry, [call]), Who.person())     # what an agent's range becomes
    v = dict(_vels(doc))
    assert v[0] == 0.9 and v[3] == 0.3 and v[4] == 0.6       # a fade over beats 0 … 3; beat 4 outside the range stays
    assert 0.3 < v[2] < v[1] < 0.9


def test_one_time_only_is_refused():
    doc = _doc()
    chord = [n["id"] for n in doc.item("b")["notes"] if (n["at"]["beat"] if isinstance(n["at"], dict) else n["at"]) == 2]
    with pytest.raises(Exception):
        doc.apply({"op": "note.ramp_velocity", "target": chord, "args": {"start": 0.2, "end": 0.9}}, Who.person())
