"""What would break silently on the Timeline: zooming never leaves the song (and zooming out all the way is "fit"
again), an automation point drag is one undo step that keeps the points in time order, the picture is a document field
that survives save and load, and a missing picture file is refused loudly."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screensound.steps_view import point  # noqa: E402
from screensound.view import View  # noqa: E402
from test_screen import bridge  # noqa: E402,F401  (the screen's fixture: a small song, a stand-in engine)


def test_zoom_stays_inside_the_song_and_fit_returns():
    v = View()
    v.zoom(4, 0.9, 20.0)
    assert not v.fit and 0 <= v.start and v.start + v.span(20.0) <= 20.0 + 1e-9
    v.scroll(100, 20.0)
    assert v.start + v.span(20.0) == pytest.approx(20.0)
    v.zoom(0.01, 0.5, 20.0)
    assert v.fit and v.start == 0 and v.span(20.0) == 20.0


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
