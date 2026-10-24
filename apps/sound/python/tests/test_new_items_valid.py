"""Every "add" a person can make creates something the sound engine accepts (a new EQ once had no bands and
broke every render after it)."""
import pytest
from rostrum_core import Document, Who

from rostrum_sound import KIND, compile
from rostrum_sound.doc import effects as FX
from rostrum_sound.engine import Engine, find_engine


@pytest.mark.skipif(not find_engine().exists(), reason="no engine built")
def test_each_effect_type_is_valid_when_added():
    doc = Document.new(KIND)
    doc.apply({"op": "track.add", "args": {"id": "t", "instrument": "builtIn", "builtIn": "warmPad"}}, Who.person())
    doc.apply({"op": "bus.add", "args": {}}, Who.person())
    types = [t for t in FX.TYPES if t != "plugin"]
    for t in types:
        doc.apply({"op": "effect.add", "target": ["t"], "args": {"effect": t}}, Who.person())
    with Engine() as eng:
        eng.request("check", schedule={**compile(doc), "length": 1.0})


def test_new_groups_are_named_plainly():
    doc = Document.new(KIND)
    for _ in range(2):
        doc.apply({"op": "bus.add", "args": {}}, Who.person())
    assert [(b["id"], b["name"]) for b in doc.data["buses"]] == [("bus_1", "Group 1"), ("bus_2", "Group 2")]


def test_an_imported_file_is_copied_into_the_song_and_raises_no_problem(tmp_path):
    from rostrum_sound import diagnose
    from rostrum_sound.doc import media
    song, outside = tmp_path / "song", tmp_path / "elsewhere"
    (song / "media").mkdir(parents=True), outside.mkdir()
    wav = outside / "tone.wav"
    wav.write_bytes(b"RIFF....WAVE")
    ref = media.keep(song, wav)
    assert ref == "media/tone.wav" and (song / ref).is_file()
    assert media.keep(song, wav) == ref                       # the same file twice is one copy
    doc = Document.new(KIND, folder=song)
    doc.apply({"op": "track.add", "args": {"id": "audio_1", "name": "Tone", "instrument": "none"}}, Who.person())
    doc.apply({"op": "clip.add", "target": ["audio_1"], "args": {"media": ref, "at": 0}}, Who.person())
    with media.of(doc):
        assert [p for p in diagnose.problems(doc) if p["kind"] == "outside-project"] == []
    doc.apply({"op": "clip.add", "target": ["audio_1"], "args": {"media": str(wav), "at": 5}}, Who.person())
    with media.of(doc):
        msg = [p["message"] for p in diagnose.problems(doc) if p["kind"] == "outside-project"][0]
    assert "audio_1" not in msg and "Tone" in msg
