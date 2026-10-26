"""The piano roll's rows keep one height, and each track comes back where the person left it, through folding and
opening the Editor, an undo and another track (critic r11 must-fix 4: rows re-fitted to 12 / 13.3 / 16 px on each
open and after undo, and clicks landed on the wrong keys). Real clicks, wheel and keys on the window."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from test_amounts_popover import click, items  # noqa: E402
from test_plugin_items import header  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
a = track("piano", builtIn="feltPiano")
b = track("lead", builtIn="feltPiano")
for i in range(16):
    a.note(36 + i * 3, at=beat(i), dur=beats(1))
for i in range(3):
    b.note(67 + i, at=beat(i), dur=beats(1))
'''


def _grid(win):
    return next(i for i in items(win) if i.isVisible() and i.property("rowH") is not None and i.property("roll") is not None and i.property("keysWidth") is not None)


def _middle(win):
    """The key at the middle of the roll's view, and the row height."""
    g = _grid(win)
    view = g.parentItem().parentItem()              # the Flickable (grid -> its content item -> it)
    row = int((view.property("contentY") + view.height() / 2) // g.property("rowH"))
    return g.property("rowH"), g.property("roll")["hi"] - row


def _wheel(win, at: QPoint, notches: int):
    for _ in range(abs(notches)):
        ev = QWheelEvent(QPointF(at), QPointF(win.mapToGlobal(at)), QPoint(0, 0), QPoint(0, 120 if notches > 0 else -120),
                         Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        QCoreApplication.sendEvent(win, ev)
        QTest.qWait(30)


def test_rows_keep_one_height_and_each_track_its_place(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    doc = Document.new(KIND, folder=tmp_path / "S", item=ITEM)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    doc.save()
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(tmp_path / "S"))
        QTest.qWait(400)
        b, win = screen.bridge, screen.win
        click(win, header(win, "piano"))
        b.workspace.setDock("editor")
        QTest.qWait(400)
        g = _grid(win)
        r = g.mapRectToScene(g.boundingRect())
        _wheel(win, QPoint(round(r.x() + r.width() / 2), 700), 3)        # the person scrolls the roll
        QTest.qWait(200)
        h, key = _middle(win)
        assert h == 12

        b.workspace.setDock("")                         # fold and open the Editor again
        QTest.qWait(300)
        b.workspace.setDock("editor")
        QTest.qWait(400)
        assert _middle(win) == (h, key), "the roll moved or re-fitted its rows on opening"

        click(win, header(win, "lead"))                 # a 3-note track: the same row height
        QTest.qWait(400)
        assert _middle(win)[0] == h, "a track with few notes got taller rows"
        click(win, header(win, "piano"))
        QTest.qWait(400)
        assert _middle(win) == (h, key), "the track did not come back where it was left"

        click(win, next(i for i in items(win) if i.isVisible() and i.property("text") == "Select"))
        QTest.keyClick(win, Qt.Key_A, Qt.ControlModifier)   # every note of the track deleted, then the undo
        QTest.qWait(200)
        QTest.keyClick(win, Qt.Key_Delete)
        QTest.qWait(300)
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(400)
        assert len(b.doc.item("piano")["notes"]) == 16
        assert _middle(win) == (h, key), "an undo re-fitted the rows"
    finally:
        screen.close()
