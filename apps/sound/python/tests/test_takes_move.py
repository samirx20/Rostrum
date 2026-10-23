"""A recorded take belongs to the song: copy or move the song's folder and the take still plays; an older song's
absolute take is made relative on open; a take whose file is gone fails loudly naming the clip, track and file."""
import shutil
import wave
from pathlib import Path

import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_sound import KIND, compile
from rostrum_sound.record import land_take


def _wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000), w.writeframes(b"\1\0" * 2400)
    return path


def _song(tmp_path):
    song = tmp_path / "song"
    doc = Document.new(KIND, song, "main")
    doc.apply([{"op": "track.add", "args": {"id": "voice", "name": "Voice"}}], Who.person())
    return song, doc


def test_a_take_survives_copying_the_song_folder(tmp_path):
    song, doc = _song(tmp_path)
    doc.apply([land_take(doc, "voice", {"file": str(_wav(tmp_path / "engine.wav")), "start": 1.0})], Who.person())
    clip = doc.data["tracks"][0]["clips"][0]
    assert clip["media"] == "media/Voice-take-1.wav"
    doc.save()
    copy = tmp_path / "elsewhere" / "song"
    shutil.copytree(song, copy)
    shutil.rmtree(song)
    opened = Document.open(copy, "main", KIND)
    assert compile(opened)["tracks"][0]["clips"][0]["media"] == str(copy / "media" / "Voice-take-1.wav")
    (copy / "media" / "Voice-take-1.wav").unlink()
    with pytest.raises(RostrumError) as e:
        compile(opened)
    assert clip["id"] in str(e.value) and "voice" in str(e.value) and "Voice-take-1.wav" in str(e.value)


def test_an_older_songs_absolute_take_is_made_relative_on_open(tmp_path):
    song, doc = _song(tmp_path)
    (song / "media").mkdir(parents=True)
    inside = _wav(song / "media" / "Voice-take-1.wav")
    outside = _wav(tmp_path / "my-own-file.wav")
    doc.apply([{"op": "clip.add", "target": ["voice"], "args": {"id": "a", "media": str(inside), "at": 0}},
               {"op": "clip.add", "target": ["voice"], "args": {"id": "b", "media": str(outside), "at": 1}}], Who.person())
    doc.save()
    copy = tmp_path / "copy"
    shutil.copytree(song, copy)                           # the copy's clips still name the original folder
    opened = Document.open(copy, "main", KIND)
    media = {c["id"]: c["media"] for c in opened.data["tracks"][0]["clips"]}
    assert media == {"a": "media/Voice-take-1.wav", "b": str(outside)}      # a file kept elsewhere is left alone
    assert Path(compile(opened)["tracks"][0]["clips"][0]["media"]).parent == copy / "media"
