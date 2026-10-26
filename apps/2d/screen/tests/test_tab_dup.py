"""Tab walks the layers at this level; Ctrl+D again repeats the move made on the copy. Real keys and mouse events into the real
window (QTest); needs the built engine."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SRC = '''
comp("c", width=1920, height=1080, fps=10, duration=2)
for i in range(5):
    shape(f"s{i}", w=120, h=120, x=300 + i * 250, y=300, fill="#667788")
shape("mover", w=120, h=120, x=300, y=700, fill="#aa6644")
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


def _key(win, key, mods=None):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    QTest.keyClick(win, key, mods or Qt.NoModifier)
    QTest.qWait(40)


def _drag(win, x, y, dx):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    a, b = _at(win, x, y), _at(win, x + dx, y)
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
    for k in range(1, 9):
        QTest.mouseMove(win, QPoint(a.x() + (b.x() - a.x()) * k // 8, a.y()))
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, b)
    QTest.qWait(50)


def test_tab_three_times_from_the_top_layer_picks_the_fourth(screen):
    from PySide6.QtCore import Qt
    b, win = screen
    top = [c["id"] for c in reversed(b.comp()["layers"]) if c["type"] != "camera"]
    b.select(top[0])
    for _ in range(3):
        _key(win, Qt.Key_Tab)
    assert b.multi.ids == [top[3]]
    _key(win, Qt.Key_Backtab, Qt.ShiftModifier)
    assert b.multi.ids == [top[2]]


def test_ctrl_d_again_repeats_the_move_made_on_the_copy(screen):
    from PySide6.QtCore import Qt
    b, win = screen
    b.select("mover")
    _key(win, Qt.Key_D, Qt.ControlModifier)
    first = b.multi.ids[0]
    _drag(win, 324, 724, 100)             # the copy sits 24 px right and down; drag it 100 px on
    assert b.multi.ids == [first]
    x1 = b.doc.item(first)["x"]
    moved = x1 - 324                                # what the drag really moved the copy (the pointer's first px is the drag distance)
    assert 80 < moved <= 100
    _key(win, Qt.Key_D, Qt.ControlModifier)
    second = b.multi.ids[0]
    assert second != first
    assert abs(b.doc.item(second)["x"] - x1 - moved) < 0.01 and b.doc.item(second)["y"] == b.doc.item(first)["y"]


def test_ctrl_d_right_after_drawing_a_shape_puts_the_copy_24_px_on(screen):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    b, win = screen
    b.clearSelection()
    _key(win, Qt.Key_R)                   # the drawn shape is inserted after the layer under it: no copy of it (round 7)
    a, z = _at(win, 900, 500), _at(win, 1100, 650)
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
    for k in range(1, 9):
        QTest.mouseMove(win, a + (z - a) * k / 8)
    before = {it["id"] for it in b.doc.items()}
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, z)
    drawn = next(it for it in b.doc.items() if it["id"] not in before)
    _key(win, Qt.Key_D, Qt.ControlModifier)     # at once: the shape is picked the frame after its release, or before
    #                                             the next key if that comes first (select_soon.py)
    copy = b.doc.item(b.multi.ids[0])
    assert copy["id"] != drawn["id"]
    assert (round(copy["x"] - drawn["x"]), round(copy["y"] - drawn["y"])) == (24, 24)
