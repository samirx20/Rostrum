"""Ctrl+Z right after making a thing whose name box opens by itself undoes in the song (critic r8 M4: after Make a
section the key went to the new section's name box and nothing happened). The kit's rule (UndoKeys.js): with nothing
typed, a text box lets go and the window's undo runs. Real input on the real window's QML (offscreen): a real range
drag on the ruler, a real click on Make a section, the real M and Ctrl+Z keys; the bridge is only read."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from screensound import music_map, playback  # noqa: E402
from test_amounts_popover import click, items, shown  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import song  # noqa: E402


def test_ctrl_z_in_a_name_box_that_opened_by_itself_undoes_the_new_thing(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(song(tmp_path / "A")))
        QTest.qWait(300)
        win, b = screen.win, screen.bridge
        ruler = next(it for it in items(win) if it.objectName() == "barRuler" and it.isVisible() and it.width())
        per, start, bars = ruler.property("perSec"), ruler.property("start"), b.song["bars"]
        r = ruler.mapRectToScene(ruler.boundingRect())
        y = round(r.y() + 3)                                           # the range band
        x0, x1 = round(r.x() + (bars[1] - start) * per), round(r.x() + (bars[3] - start) * per)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, QPoint(x0, y))
        for k in range(1, 7):
            QTest.mouseMove(win, QPoint(x0 + (x1 - x0) * k // 6, y))
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, QPoint(x1, y))
        QTest.qWait(150)
        click(win, shown(win, "action:section"))
        assert len(music_map.sections(b.doc.data)) == 1
        box = shown(win, "sectionNameBox")
        assert box.hasActiveFocus()                                    # the name box took the keys by itself
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(150)
        assert music_map.sections(b.doc.data) == [], "Ctrl+Z after Make a section must take the section away"
        assert not b.renaming                                          # the box closed with it
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)   # and redo brings it back
        QTest.qWait(150)
        assert len(music_map.sections(b.doc.data)) == 1

        marks = len(b._view["markers"])
        QTest.keyClick(win, Qt.Key_M)                                  # a new marker, its name box open
        QTest.qWait(150)
        assert len(b._view["markers"]) == marks + 1 and b.renaming
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(150)
        assert len(b._view["markers"]) == marks and not b.renaming
    finally:
        screen.close()
        QTest.qWait(50)
