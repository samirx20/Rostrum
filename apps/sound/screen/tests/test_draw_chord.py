"""Note ▾ › Draw › Major (SPEC 3.9): chosen with real clicks on the Note ▾ button and its menu row, a real Draw click on the
roll stamps a major triad (three notes), and one undo takes all three away. Real input on the real window's QML
(offscreen); the bridge is only read. The engine is a stand-in. Also times the stamping release."""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from screensound import playback  # noqa: E402
from test_amounts_popover import click, shown  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import rolls, song  # noqa: E402


def test_a_draw_click_with_major_chosen_stamps_a_triad_in_one_step(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(song(tmp_path / "A")))
        b, win = screen.bridge, screen.win
        b.select("lead")
        b.workspace.setDock("editor")
        b.setTool("draw")
        QTest.qWait(300)
        assert b.noteLabel == "Note 1/4"
        click(win, shown(win, "noteMenu"))
        click(win, shown(win, "menu:draw:major"))
        QTest.qWait(100)
        assert b.drawChord == "major" and b.noteLabel == "Note 1/4 · Chord"
        before, steps = len(b.doc.item("lead")["notes"]), len(b.doc.history.changes)
        [roll] = rolls(win)
        grid = roll.property("grid")
        top = grid.mapToScene(QPoint(0, 0))
        r = roll.mapRectToScene(roll.boundingRect())
        at = QPoint(round(r.x() + r.width() * 0.4), round(top.y() + (grid.property("roll")["hi"] - 62 + 0.5) * grid.property("rowH")))
        QTest.mouseMove(win, at)
        t0 = time.perf_counter()
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, at)
        QApplication.processEvents()
        t1 = time.perf_counter()
        print(f"stamp press: {(t1 - t0) * 1000:.1f} ms")
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, at)
        QApplication.processEvents()
        print(f"stamp release: {(time.perf_counter() - t1) * 1000:.1f} ms")
        QTest.qWait(200)
        notes = b.doc.item("lead")["notes"]
        assert len(notes) == before + 3, len(notes)
        assert len(b.doc.history.changes) == steps + 1
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(200)
        assert len(b.doc.item("lead")["notes"]) == before
    finally:
        screen.close()
        QTest.qWait(50)
