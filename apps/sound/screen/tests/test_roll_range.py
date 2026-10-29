"""Notes past a track's recorded samples (hand composer r2 #5: timpani A1 drawn under its lowest sample C2): the roll
knows the sound's range (the engine's own, asked once per sound off the window's thread, roll_range.py) and shades the
rows outside it quietly; a note drawn there is added like any other (it plays from the nearest sample, stretched). A
sound that plays any key: no range."""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_sound import note_ranges  # noqa: E402
from screensound import playback  # noqa: E402
from test_click_lands import song  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_select import bridge  # noqa: E402,F401  (the fixture: a small song, the engine stood in for)
from test_song_swap import rolls  # noqa: E402

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


def test_a_note_drawn_below_the_range_with_a_real_click_is_added(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    monkeypatch.setitem(note_ranges._KEPT, PIANO, (126, 127))      # the piano's samples end far above every row shown
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(song(tmp_path / "A")))
        b, win = screen.bridge, screen.win
        QTest.qWait(300)
        b.select("lead")
        QTest.keyClick(win, Qt.Key_E)                                  # the Editor
        QTest.qWait(300)
        QTest.keyClick(win, Qt.Key_B)                                  # Draw
        QTest.qWait(50)
        assert b.rollPlayable == [126, 127]
        [roll] = rolls(win)
        rr = roll.property("bars").mapRectToScene(roll.property("bars").boundingRect())
        n = len(b.doc.item("lead")["notes"])
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(round(rr.x() + 300), round(rr.bottom() + 40)))
        QTest.qWait(80)
        assert len(b.doc.item("lead")["notes"]) == n + 1               # drawn: the shade is a hint, not a wall
        assert not b.statusFailed
    finally:
        screen.close()
        QTest.qWait(50)


def test_a_sound_that_plays_any_key_shades_nothing(bridge, monkeypatch):  # noqa: F811
    kept(bridge, monkeypatch, None)
    assert bridge.rollPlayable == []
    bridge.setTool("draw")
    assert bridge.drawAt(20.0, 20, 0.01)
