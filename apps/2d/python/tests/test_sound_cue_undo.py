"""Add a sound here is one Undo step for the person (sound_cues.py, rostrum_core.joint): the marker it is timed by and
the clip in Sound's song are one step, so one Undo across 2D's one history (rostrum_core.desk) takes both back and Redo
brings both back; with the song not open on the screen, Undo opens it (project_sound.open_item)."""
import wave

from rostrum_core import Who, desk, markers

from rostrum2d import project_sound, sound_cues
from test_soundtrack import project

ME = Who.person("sam")


def _cued(tmp_path):
    app, rt = project(tmp_path)
    doc = app.documents["film"]
    doc.apply([{"op": "layer.add", "target": ["main"], "args": {"type": "shape", "id": "logo"}}], ME)
    click = tmp_path / "click.wav"
    with wave.open(str(click), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(8000), w.writeframes(b"\x00\x10" * 800)
    sound_cues.cue(tmp_path, doc, "logo", click, ME)
    return doc


def _cue_clips(tmp_path):
    song = project_sound.open_song(tmp_path, "song")
    return [c["id"] for t in song.data["tracks"] if t["id"] == sound_cues.TRACK for c in t.get("clips", [])]


def _marks(tmp_path):
    return {m["name"]: m for m in markers.listing(tmp_path)}


def test_one_undo_takes_back_the_cue_and_its_marker(tmp_path):
    doc = _cued(tmp_path)
    docs = [doc, markers.open_to_change(tmp_path), project_sound.open_song(tmp_path, "song")]
    assert _cue_clips(tmp_path) == ["cue_logo"]
    assert _marks(tmp_path)["logo · sound"]["follows"]["part"] == "logo"   # it follows its layer (links.py)
    desk.undo(docs, ME)
    assert _cue_clips(tmp_path) == [] and "logo · sound" not in _marks(tmp_path)
    assert doc.has("logo")                                        # the one step was the cue, not the layer
    desk.redo(docs, ME)
    assert _cue_clips(tmp_path) == ["cue_logo"] and "logo · sound" in _marks(tmp_path)


def test_undo_opens_the_song_when_it_is_not_open_here(tmp_path):
    doc = _cued(tmp_path)
    hit = desk.undo([doc, markers.open_to_change(tmp_path)], ME, lambda item: project_sound.open_item(tmp_path, item))
    assert hit is not None and _cue_clips(tmp_path) == []


def test_no_song_here_names_the_folder_the_agents_sound_works_in(tmp_path, monkeypatch):
    """Re-bench D1: the cue error said "make the sound in RostrumSound first" to agents who had, in Sound's own folder."""
    from rostrum_core import agent_last
    monkeypatch.setenv("ROSTRUM_AGENT_HOME", str(tmp_path / "agent"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "cue-agent")
    here = tmp_path / "film"
    assert f'run_open_project {{"folder": "{here}"}}' in project_sound.where_the_music_is(here)
    (tmp_path / "sound").mkdir()
    agent_last.remember("rostrum-sound", tmp_path / "sound", "song")
    said = project_sound.where_the_music_is(here)
    assert str((tmp_path / "sound").resolve()) in said and "another project" in said and str(here) in said
