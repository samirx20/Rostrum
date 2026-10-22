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
    assert timeline.song(root)["length"] == pytest.approx(8 * bar)       # a short phrase: still 8 bars to write in
    root["tracks"][0]["notes"][0]["at"] = {"beat": 40}                  # 10 bars in: the last bar + 2 spare bars
    assert timeline.song(root)["length"] == pytest.approx(13 * bar)


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
    assert bridge.status.startswith("Error") and bridge.picture == str(clip)
