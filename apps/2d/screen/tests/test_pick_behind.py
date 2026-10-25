"""Alt+click picks the layer behind the pick, Alt+drag makes exactly one copy when the pointer first moves (the original
stays), picked or not (sweep r3 finding 6). Real mouse events into the real window; needs the built engine."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SRC = '''
comp("c", width=1920, height=1080, fps=10, duration=2)
shape("bottom", w=300, h=300, x=400, y=300, anchorX=0, anchorY=0, fill="#445566")
shape("middle", w=300, h=300, x=450, y=350, anchorX=0, anchorY=0, fill="#667788")
shape("top", w=300, h=300, x=500, y=400, anchorX=0, anchorY=0, fill="#8899aa")
shape("alone", w=100, h=100, x=1200, y=300, anchorX=0, anchorY=0, fill="#aa6644")
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


def _at(win, x, y):
    from screen2d.stroke_steps import _scene_of
    return _scene_of(win, x, y)


def _alt_click(win, x, y):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    QTest.mouseClick(win, Qt.LeftButton, Qt.AltModifier, _at(win, x, y))


def _alt_drag(win, x, y, dx):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    a, b = _at(win, x, y), _at(win, x + dx, y)
    QTest.mousePress(win, Qt.LeftButton, Qt.AltModifier, a)
    for k in range(1, 9):
        QTest.mouseMove(win, QPoint(a.x() + (b.x() - a.x()) * k // 8, a.y()))
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, b)


def test_alt_click_walks_back_through_the_layers_and_round(screen):
    b, win = screen
    from PySide6.QtTest import QTest
    for want in ("middle", "bottom", "top"):         # nothing picked: the second from the top, then down, then round
        _alt_click(win, 600, 500)
        QTest.qWait(50)
        assert b.multi.ids == [want]


def test_alt_drag_makes_one_copy_and_leaves_the_original(screen):
    b, win = screen
    from PySide6.QtTest import QTest
    for picked in (False, True):
        n = len(b.comp()["layers"])
        if picked:
            b.select("alone")
        else:
            b.clearSelection()
        _alt_drag(win, 1250, 350, 200)
        QTest.qWait(50)
        assert len(b.comp()["layers"]) == n + 1
        assert b.doc.item("alone")["x"] == 1200            # the original stays where it was
        copy = b.multi.ids[0]
        assert copy != "alone" and abs(b.doc.item(copy)["x"] - 1400) < 2
        b.undo()
        QTest.qWait(50)
        assert len(b.comp()["layers"]) == n
