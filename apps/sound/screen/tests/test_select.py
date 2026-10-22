"""Select first, then act: what would break silently. A drag of several items is one undo step; cut and paste are
one undo step each; Shift while dragging keeps the pitch (only in time) and Ctrl, not Shift, turns snapping off.
The engine is replaced by a stand-in (sound is checked by listening)."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402

SRC = '''
tempo(120); beats_per_bar(4)
lead = track("lead", builtIn="feltPiano")
lead.note("C4", at=beat(4), dur=beats(1))
lead.note("E4", at=beat(6), dur=beats(1))
lead.note("G4", at=beat(8), dur=beats(1))
'''
A, B, C = "lead.n2000", "lead.n3000", "lead.n4000"


class FakeEngine:
    def request(self, do, schedule=None, out=None, **kw):
        Path(out).write_bytes(b"")
        return {"file": out, "lufs": -20.0, "tracks": [], "stems": {}}

    def take_restarted(self):
        return ""

    def close(self):
        pass


@pytest.fixture
def bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    b = SoundBridge(doc)
    yield b
    b.close()


def drag(b, item, dt, dsemi, free=False, only_time=False):
    assert b.beginDrag(item)
    for f in (0.3, 0.6, 1.0):
        b.dragTo(dt * f, round(dsemi * f), free, only_time, False, 0.0)
    b.endDrag()


def test_drag_of_many_is_one_undo_step(bridge):
    doc, before = bridge.doc, len(bridge.doc.history.changes)
    bridge.selectMany([A, B, C])
    drag(bridge, B, 0.5, 2)                              # +1 beat, +2 semitones, all three
    assert [doc.item(i)["at"] for i in (A, B, C)] == [{"beat": 5.0}, {"beat": 7.0}, {"beat": 9.0}]
    assert [doc.item(i)["pitch"] for i in (A, B, C)] == ["D4", "F#4", "A4"]
    assert len(doc.history.changes) == before + 1
    bridge.undo()
    assert [doc.item(i)["at"] for i in (A, B, C)] == [{"beat": 4}, {"beat": 6}, {"beat": 8}]


def test_shift_is_only_in_time_and_ctrl_is_free(bridge):
    doc = bridge.doc
    bridge.select(A)
    drag(bridge, A, 0.5, 3, only_time=True)              # Shift: the pitch stays
    assert doc.item(A)["pitch"] == "C4"
    drag(bridge, A, 0.1, 0, free=True)                   # Ctrl: off the quarter-beat grid
    assert doc.item(A)["at"] == {"beat": 5.2}


def test_cut_and_paste_are_one_undo_step_each(bridge):
    doc, n = bridge.doc, len(bridge.doc.history.changes)
    bridge.selectMany([A, B])
    assert bridge.run("cut")
    assert not doc.has(A) and not doc.has(B) and len(doc.history.changes) == n + 1
    bridge.setTime(6.0)
    bridge.select("lead")
    assert bridge.run("paste")
    assert len(doc.history.changes) == n + 2
    new = bridge.selectedIds                             # what the paste made is selected
    assert [doc.item(i)["at"] for i in new] == [{"beat": 12.0}, {"beat": 14.0}]
    bridge.undo()
    assert not any(doc.has(i) for i in new)


def test_a_locked_tracks_note_refuses_an_edit_loudly(bridge):
    doc = bridge.doc
    bridge.select("lead")
    assert bridge.run("lock")
    bridge.select(A)
    assert not bridge.nudge("grid", 1)                   # refused, said, nothing moved
    assert "locked" in bridge.status and doc.item(A)["at"] == {"beat": 4}
    from rostrum_core import RostrumError, Who
    with pytest.raises(RostrumError):                    # an agent too
        doc.apply([{"op": "note.set", "target": [A], "args": {"vel": 0.1}}], Who.agent("claude"))


def test_trim_by_handle_and_note_length_are_one_undo_step_each(bridge):
    doc, n = bridge.doc, len(bridge.doc.history.changes)
    bridge.selectMany([A, B])
    assert bridge.beginHandle(A, "length")
    for f in (0.3, 1.0):
        bridge.handleTo(0.25 * f, 0, False)
    bridge.endDrag()
    assert [doc.item(i)["dur"] for i in (A, B)] == [{"beats": 1.5}, {"beats": 1.5}]
    assert len(doc.history.changes) == n + 1
    bridge.undo()
    assert doc.item(A)["dur"] == {"beats": 1} and set(bridge.selectedIds) == {A, B}      # undo selects them again


def test_landing_a_bar_on_a_marker_is_one_undo_step(bridge):
    from rostrum_sound.doc import tempo
    doc, n = bridge.doc, len(bridge.doc.history.changes)
    bridge.setTime(9.0)
    bridge.markerAt(9.0)
    bridge.finishRename(bridge.renaming, "logo")         # M, then the name, Enter
    assert bridge.landBar("fit_bar", 5)
    assert abs(tempo.seconds_at(doc.data, 16) - 9.0) < 1e-6   # bar 5 starts on the marker; beats follow
    assert len(doc.history.changes) == n + 3             # add, rename, land: one step each
    bridge.undo()
    assert doc.data["tempo"] == 120
