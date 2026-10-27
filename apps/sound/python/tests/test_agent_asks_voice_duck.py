"""What agents rely on and would not notice breaking: a duck under a voice-line track spans the whole line (voice mode,
a hold), a duck under a kick stays a pump, and a script `v.line(...)` fails by saying `line.add` is the way."""
import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_sound import KIND
from rostrum_sound.script import run_source


def doc_with(under):
    doc = Document.new(KIND)
    doc.apply([{"op": "track.add", "args": {"id": "vo", "instrument": "voice", "voice": "ryan"}},
               {"op": "track.add", "args": {"id": "pad", "instrument": "builtIn", "builtIn": "pad"}},
               {"op": "duck.add", "target": ["pad"], "args": {"under": under}}], Who.person())
    return doc


def test_a_duck_under_a_voice_track_spans_the_line():
    d = doc_with(["vo"])
    duck = d.data["tracks"][1]["ducks"][0]
    assert duck["voice"] is True and duck["hold"] > 0


def test_a_duck_under_a_music_track_stays_a_pump():
    doc = Document.new(KIND)
    doc.apply([{"op": "track.add", "args": {"id": "bass", "instrument": "builtIn", "builtIn": "uprightBass"}},
               {"op": "track.add", "args": {"id": "pad", "instrument": "builtIn", "builtIn": "pad"}},
               {"op": "duck.add", "target": ["pad"], "args": {"under": ["bass"]}}], Who.person())
    duck = doc.data["tracks"][1]["ducks"][0]
    assert duck["voice"] is False and duck["hold"] == 0


def test_a_script_line_call_says_to_use_line_add():
    with pytest.raises(RostrumError) as e:
        run_source("v = track('narrator', instrument='voice', voice='ryan')\nv.line('hi', at=1)", "s")
    assert "line.add" in str(e.value)
