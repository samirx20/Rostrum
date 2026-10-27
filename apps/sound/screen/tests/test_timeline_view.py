"""What would break silently on the Timeline: the song keeps room to write in, an automation point drag is one undo
step that keeps the points in time order, the picture is a document field that survives save and load, and a missing
picture file is refused loudly. (Zoom and scroll are the kit's TimeView, tested there.)"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screensound.steps_view import point  # noqa: E402
from test_screen import bridge  # noqa: E402,F401  (the screen's fixture: a small song, a stand-in engine)


def test_song_keeps_room_to_write():
    from screensound import timeline
    bar = 4 * 0.6                                           # 100 bpm, 4/4
    root = {"tempo": 100, "beatsPerBar": 4, "tracks": [{"id": "t", "notes": [
        {"id": "n", "type": "note", "pitch": "C4", "at": {"beat": 0}, "dur": {"beats": 1}}]}]}
    assert timeline.song(root)["length"] == pytest.approx(9 * bar)       # a short phrase: its bar + 8 to write in
    root["tracks"][0]["notes"][0]["at"] = {"beat": 40}                  # 10 bars in: the last bar + 8 spare bars
    assert timeline.song(root)["length"] == pytest.approx(19 * bar)


def test_automation_drag_is_one_undo_step_in_time_order(bridge):  # noqa: F811
    doc = bridge.doc
    bridge.openLane("lead", "lead", "volume")
    point(bridge, "lead", 1.0, 0.5)
    point(bridge, "lead", 3.0, 1.0)
    before = len(doc.history.changes)
    point(bridge, "lead", 1.0, 0.5, 5.0, 1.5)                  # drag the first point past the second: it stops short
    assert len(doc.history.changes) == before + 1
    ts = [p[0]["beat"] * 0.5 if isinstance(p[0], dict) else p[0] for p in doc.item("lead.auto_volume")["points"]]
    assert ts == sorted(ts) and len(ts) == 2
    bridge.undo()
    assert [round(p[1], 2) for p in doc.item("lead.auto_volume")["points"]] == [0.5, 1.0]


def test_picture_is_a_field_and_a_missing_file_is_refused(bridge, tmp_path):  # noqa: F811
    clip = tmp_path / "pic.mp4"
    clip.write_bytes(b"")
    bridge.setPicture(str(clip))
    assert bridge.doc.data["picture"] == str(clip) and bridge.picture == str(clip)
    bridge.setPicture(str(tmp_path / "gone.mp4"))
    assert bridge.statusFailed and "is not a file" in bridge.status and bridge.picture == str(clip)


def test_clip_draws_the_sound_it_plays(tmp_path, monkeypatch):
    """A clip playing a cleaned take draws the take's waveform (silent here), not the original's; switched off, the original's."""
    import numpy as np
    import soundfile as sf
    from rostrum_sound import cleanup
    from screensound import timeline
    orig, cleaned = tmp_path / "o.wav", tmp_path / "c.wav"
    sf.write(orig, 0.5 * np.sin(np.arange(48000) / 5).astype("float32"), 48000)
    sf.write(cleaned, np.zeros(48000, dtype="float32"), 48000)
    monkeypatch.setattr(cleanup, "cached", lambda media, recipe: str(cleaned))
    clip = {"id": "c1", "media": str(orig), "at": 0, "denoise": 0.6}
    assert max(timeline.clip_span(clip, {"tempo": 120})[2]) == 0
    assert max(timeline.clip_span({**clip, "useCleaned": False}, {"tempo": 120})[2]) > 0.9


def test_song_ends_where_the_render_ends_not_where_the_view_ends(bridge):
    """The end of the song is the render's own length (last sound + 2 s), never the ruler's 8 bars of room to write in:
    a player opened on an older, longer render reports that older end, and the playhead must not jump there."""
    t = bridge.transport
    t.last = {"seconds": 5.9}
    assert bridge._length() > 5.9 and t.end() == 5.9
    heard = []
    t.moved.connect(heard.append)
    t._ended(16.0)
    assert heard == [5.9]
