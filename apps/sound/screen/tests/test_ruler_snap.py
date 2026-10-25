"""A click on the ruler puts the playhead on the grid (spec workflow 1): 3 px right of bar 5 lands on bar 5; with Ctrl
held it lands exactly where it was clicked. Real input on the real window's QML (offscreen): the real ruler, the real
mouse and Ctrl key; the bridge is only read. The engine is a stand-in."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from screensound import playback  # noqa: E402
from test_amounts_popover import items  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import song  # noqa: E402


def test_a_ruler_click_lands_on_the_grid_and_ctrl_frees_it(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(song(tmp_path / "A")))
        QTest.qWait(300)
        win, b = screen.win, screen.bridge
        ruler = next(it for it in items(win) if it.objectName() == "barRuler" and it.isVisible() and it.width() > 0)
        bar5 = b.song["bars"][4]
        per, start = ruler.property("perSec"), ruler.property("start")
        r = ruler.mapRectToScene(ruler.boundingRect())
        y = round(r.y() + r.height() - 6)                              # on the scale, under the range band
        at = QPoint(round(r.x() + (bar5 - start) * per) + 3, y)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        QTest.qWait(50)
        assert abs(b.time - bar5) < 1e-6, (b.time, bar5)
        QTest.mouseClick(win, Qt.LeftButton, Qt.ControlModifier, at)
        QTest.qWait(50)
        assert abs(b.time - bar5) > 1 / per, (b.time, bar5)          # free: where the pointer was, not the bar line
    finally:
        screen.close()
        QTest.qWait(50)
