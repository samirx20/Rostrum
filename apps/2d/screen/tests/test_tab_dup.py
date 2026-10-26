"""Tab walks the layers at this level; Ctrl+D again repeats the step from the original to the copy, however the copy was made. Real keys and mouse events into the real
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


def _drag(win, x, y, dx, mods=None):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    mods = mods or Qt.NoModifier
    a, b = _at(win, x, y), _at(win, x + dx, y)
    QTest.mousePress(win, Qt.LeftButton, mods, a)
    for k in range(1, 9):
        QTest.mouseMove(win, QPoint(a.x() + (b.x() - a.x()) * k // 8, a.y()))
    QTest.mouseRelease(win, Qt.LeftButton, mods, b)
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


def _row(b, ids):
    """Each copy's step from the one before: (across, down)."""
    xy = [(b.doc.item(i)["x"], b.doc.item(i)["y"]) for i in ids]
    return [(round(q[0] - p[0], 2), round(q[1] - p[1], 2)) for p, q in zip(xy, xy[1:])]


def _ctrl_d(b, win, times):
    from PySide6.QtCore import Qt
    made = []
    for _ in range(times):
        _key(win, Qt.Key_D, Qt.ControlModifier)
        made.append(b.multi.ids[0])
    return made


def test_ctrl_d_moved_copy_then_ctrl_d_repeats_the_gap_from_the_original(screen):
    from PySide6.QtCore import Qt
    b, win = screen
    b.select("mover")
    _key(win, Qt.Key_D, Qt.ControlModifier)
    first = b.multi.ids[0]
    _drag(win, 300, 700, 200)             # the copy lands in place, on top; drag it on, so it sits ~200 px across
    assert b.multi.ids == [first]
    row = ["mover", first] + _ctrl_d(b, win, 2)
    steps = _row(b, row)
    assert 170 < steps[0][0] <= 200 and steps[0][1] == 0     # (the drop may snap to a neighbour's edge)
    assert steps == [steps[0]] * 3, steps          # an even row: each copy takes the step from the original to the copy


def test_alt_drag_a_copy_then_ctrl_d_repeats_its_step(screen):
    from PySide6.QtCore import Qt
    b, win = screen
    b.select("mover")
    _drag(win, 300, 700, 300, Qt.AltModifier)       # Alt+drag: the original stays, the copy moves ~300 px right
    first = b.multi.ids[0]
    assert first != "mover" and b.doc.item("mover")["x"] == 300
    row = ["mover", first] + _ctrl_d(b, win, 2)
    steps = _row(b, row)
    assert 270 < steps[0][0] < 330 and steps[0][1] == 0     # (the drop may snap to a neighbour's edge)
    assert steps == [steps[0]] * 3, steps


def test_ctrl_d_right_after_drawing_a_shape_copies_it_in_place(screen):
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
    assert (round(copy["x"] - drawn["x"]), round(copy["y"] - drawn["y"])) == (0, 0)   # (round 7: not thrown 460 px away)
