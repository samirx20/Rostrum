"""A text typed with the Text tool lands where a script's text with the same x, y does (one anchor rule for every text,
text_anchor.py; critic r7 must-fix 4). Real key and mouse events into the real window; needs the built engine."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SRC = '''
comp("c", width=1920, height=1080, fps=10, duration=2)
text("ref", body="ORBIT", x=600, y=300, size=88)
'''


@pytest.fixture
def screen(tmp_path):
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SRC, "a.py"))
    session.files.put(doc)
    from PySide6.QtTest import QTest
    QTest.qWait(800)
    yield session.bridge, session.win
    app.processEvents()
    session.close()


def _type(win, words):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QGuiApplication, QKeyEvent
    from PySide6.QtTest import QTest
    for ch in words:
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QGuiApplication.sendEvent(win, QKeyEvent(kind, Qt.Key(ord(ch.upper())), Qt.ShiftModifier, ch))
        QTest.qWait(10)


def test_the_text_tool_and_a_script_place_a_text_alike(screen):
    b, win = screen
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from rostrum2d import boxes
    from screen2d.stroke_steps import _scene_of
    QTest.keyClick(win, Qt.Key_T)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, _scene_of(win, 600, 1000))
    QTest.qWait(100)
    _type(win, "ORBIT")
    QTest.keyClick(win, Qt.Key_Escape)
    QTest.qWait(300)
    made = next(lay for lay in b.comp()["layers"] if lay["type"] == "text" and lay["id"] != "ref")
    ref, mine = boxes.box(b.doc.item("ref"), 0.0), boxes.box(made, 0.0)
    assert abs(made["x"] - 600) < 2.5 and abs(made["y"] - 1000) < 2.5, made     # a screen pixel here, + the click's whole-pixel rounding
    assert abs((ref[0] + ref[2]) / 2 - (mine[0] + mine[2]) / 2) < 2.5, (ref, mine)        # the same across, about x
    assert abs((ref[1] + ref[3]) / 2 - (mine[1] + mine[3]) / 2 + 700) < 2.5, (ref, mine)  # and about y (700 lower)
