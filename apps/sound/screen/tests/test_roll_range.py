"""Notes a track's recorded sound can't play (hand composer r2 #5: timpani A1 drawn under its lowest sample C2 without a
word, then every render failed): the roll knows the sound's range (the engine's own, asked once per sound off the
window's thread, roll_range.py), its faint Draw note is red on those rows, and a Draw click, a drag or a transpose that
would put notes there is refused in the top bar, in words, with nothing changed. A sound that plays any key: no range."""
import time

from PySide6.QtCore import QCoreApplication
from rostrum_sound import note_ranges
from screensound import playback
from test_select import A, C, bridge  # noqa: F401  (the fixture: a small song, the engine stood in for)

PIANO = '{"builtIn": "feltPiano"}'


def kept(b, monkeypatch, rng):
    """The engine's answer for the piano, as if it had come (Asker.answered)."""
    monkeypatch.setitem(note_ranges._KEPT, PIANO, rng)
    b._playable_check()


def test_the_range_is_asked_once_off_the_thread_and_shown(bridge, monkeypatch):  # noqa: F811
    asked = []

    class Engine:
        def request(self, do, **kw):
            asked.append(kw["instrument"])
            return {"lowKey": 60, "highKey": 67}

        def close(self):
            pass

    monkeypatch.setattr(note_ranges, "_KEPT", {})
    monkeypatch.setattr(playback, "open_engine", Engine)
    bridge.__dict__.pop("_asker", None)                   # (the fixture's song asked the stand-in engine already)
    bridge._playable_check()
    end = time.time() + 3
    while bridge.rollPlayable != [60, 67] and time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert bridge.rollPlayable == [60, 67]
    bridge.select("")
    bridge.select("lead")
    assert asked == [{"builtIn": "feltPiano"}]            # once per sound


def test_a_draw_click_on_a_row_its_sound_cant_play_is_refused_in_words(bridge, monkeypatch):  # noqa: F811
    kept(bridge, monkeypatch, (60, 72))
    b = bridge
    b.select("lead")
    assert b.rollPlayable == [60, 72]
    b.setTool("draw")
    n = len(b.doc.item("lead")["notes"])
    ghost = b.rollHover(20.0, 57, 0.0001, 0.01, True)["ghost"]
    assert ghost["out"] is True                             # its faint note is red there
    assert b.rollHover(20.0, 62, 0.0001, 0.01, True)["ghost"]["out"] is False
    assert b.drawAt(20.0, 57, 0.01) == ""
    assert len(b.doc.item("lead")["notes"]) == n            # nothing drawn
    assert b.statusFailed and b.status == "lead plays C4–C5: A3 is below it"
    assert b.drawAt(20.0, 62, 0.01)                          # in range: drawn
    b.endDrag()
    assert len(b.doc.item("lead")["notes"]) == n + 1


def test_a_transpose_or_a_drag_out_of_the_range_is_refused(bridge, monkeypatch):  # noqa: F811
    kept(bridge, monkeypatch, (60, 67))
    b = bridge
    b.select("lead")
    b.selectMany([A, C])                                     # C4 and G4
    assert not b.pitchStep(1)                                # G4 → G#4: above
    assert [b.doc.item(i)["pitch"] for i in (A, C)] == ["C4", "G4"]
    assert b.status == "lead plays C4–G4: G#4 is above it"
    b.pitchStep(-1)                                          # C4 → B3 is below: refused the same way
    assert b.doc.item(A)["pitch"] == "C4" and "B3 is below it" in b.status
    assert b.beginDrag(C)
    b.dragTo(0.0, 3, False, False, False, 0.0)              # three keys up: past the top
    assert b.status == "lead plays C4–G4: A#4 is above it"
    b.endDrag()
    assert [b.doc.item(i)["pitch"] for i in (A, C)] == ["C4", "G4"]


def test_a_sound_that_plays_any_key_shades_nothing(bridge, monkeypatch):  # noqa: F811
    kept(bridge, monkeypatch, None)
    assert bridge.rollPlayable == []
    bridge.setTool("draw")
    assert bridge.drawAt(20.0, 20, 0.01)
