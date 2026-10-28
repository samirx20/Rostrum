"""A duck under speech dips for whole lines without the agent knowing the `voice` flag (3E audit: a duck under a
voice-over file dipped 0.9 dB): role="dialogue" marks speech, a duck with no `under` dips under every dialogue track,
resolved at compile so a dialogue track added later counts, and with no dialogue track the render says how to fix it."""
import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_sound import KIND
from rostrum_sound.compile import compile
from rostrum_sound.script import run_source


def _ducks(data, track):
    return next(t for t in compile(data)["tracks"] if t["id"] == track)["ducks"]


def test_a_script_duck_with_no_under_dips_under_every_dialogue_track_for_whole_lines():
    data = run_source('vo = track("vo", role="dialogue")\nm = track("m", builtIn="piano")\nm.note("C4", at=0, dur=1)\n'
                      'm.duck(depth=0.7)', "s.py")
    data = getattr(data, "data", data)
    assert data["tracks"][1]["ducks"][0]["under"] == []                     # stored as written: "every dialogue track"
    d = _ducks(data, "m")[0]
    assert d["under"] == ["vo"] and d["voice"] is True and d["hold"] > 0 and d["depth"] == 0.7


def test_voice_false_written_stays_a_pump_and_music_under_music_stays_a_pump():
    data = run_source('vo = track("vo", role="dialogue")\nb = track("b", builtIn="bass")\nm = track("m", builtIn="piano")\n'
                      'm.note("C4", at=0, dur=1)\nm.duck(under=["vo"], voice=False)\nm.duck(under=["b"])', "s.py")
    data = getattr(data, "data", data)
    a, b = _ducks(data, "m")
    assert a["voice"] is False and b["voice"] is False and b["hold"] == 0


def test_duck_add_with_no_under_picks_up_a_dialogue_track_added_later_and_fails_loudly_without_one():
    doc = Document.new(KIND)
    doc.apply([{"op": "track.add", "args": {"id": "pad", "instrument": "builtIn", "builtIn": "pad"}},
               {"op": "duck.add", "target": ["pad"], "args": {}}], Who.person())
    with pytest.raises(RostrumError, match='role="dialogue"'):
        compile(doc.data)
    memo = {}
    with pytest.raises(RostrumError):
        compile(doc.data, memo=memo)
    doc.apply([{"op": "track.add", "args": {"id": "vo"}}, {"op": "track.set", "target": ["vo"], "args": {"role": "dialogue"}}],
              Who.person())
    d = next(t for t in compile(doc.data, memo=memo)["tracks"] if t["id"] == "pad")["ducks"][0]
    assert d["under"] == ["vo"] and d["voice"] is True
