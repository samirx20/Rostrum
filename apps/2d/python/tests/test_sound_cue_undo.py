"""Add a sound here is one Undo step for the person (sound_cues.py): the clip in Sound's song is their change; the
shared marker it is timed by is kept by 2D's link, so one Undo across 2D's one history (the document, the markers,
the song: rostrum_core.desk) takes the cue back and Redo brings it back, with its marker still there."""
import wave

from rostrum_core import Who, desk, markers

from rostrum2d import project_sound, sound_cues
from test_soundtrack import project

ME = Who.person("sam")


def test_one_undo_takes_back_the_cue(tmp_path):
    app, rt = project(tmp_path)
    doc = app.documents["film"]
    doc.apply([{"op": "layer.add", "target": ["main"], "args": {"type": "shape", "id": "logo"}}], ME)
    click = tmp_path / "click.wav"
    with wave.open(str(click), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(8000), w.writeframes(b"\x00\x10" * 800)
    sound_cues.cue(tmp_path, doc, "logo", click, ME)

    def cue_clips():
        song = project_sound.open_song(tmp_path, "song")
        return [c["id"] for t in song.data["tracks"] if t["id"] == sound_cues.TRACK for c in t.get("clips", [])]

    docs = [doc, markers.open_to_change(tmp_path), project_sound.open_song(tmp_path, "song")]
    assert cue_clips() == ["cue_logo"]
    doc_where, _ = desk.undo(docs, ME)
    assert doc_where.item_id == "song" and cue_clips() == []
    assert doc.has("logo")                                        # the one step was the cue, not the layer
    assert "logo · sound" in [m["name"] for m in markers.listing(tmp_path)]   # kept for Redo
    desk.redo(docs, ME)
    assert cue_clips() == ["cue_logo"]
