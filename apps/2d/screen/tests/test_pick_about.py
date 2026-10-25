"""What the pick is about (spec base F): after a layer drag and Ctrl+Z, a click on the layer makes Ctrl+C copy the LAYER,
never a key (sweep r3 FINDINGS 9: a key square under the layer's middle took the click); and → moves two picked keys one
frame, one undo step. Real mouse and keys on the window. Needs the built engine."""
import os
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SOURCE = ('comp("main", name="Main", width=1920, height=1080, fps=30, duration=4, background="#0b0d14")\n'
          'a = shape("a", w=300, h=200, fill="#336699", x=500, y=400)\n'
          'a.key("x", {0.0: 500, 2.0: 800})\n'
          'b = shape("b", w=300, h=200, fill="#996633", x=1300, y=400)\n')


@pytest.fixture
def screen(tmp_path):
    from PySide6.QtTest import QTest
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SOURCE, "a.py"))
    session.files.put(doc)
    QTest.qWait(800)
    try:
        yield session.bridge, session.win
    finally:
        app.processEvents()
        session.close()


def _middle(win, b, layer):
    from PySide6.QtCore import QObject, QPoint, QPointF
    stage = win.findChild(QObject, "stage")
    box = next(d for d in b.shown_boxes() if d["id"] == layer)
    o, s = stage.property("compOrigin"), stage.property("compScale")
    p = stage.mapToScene(QPointF(o.x() + (box["x"] + box["w"] / 2) * s, o.y() + (box["y"] + box["h"] / 2) * s))
    return QPoint(round(p.x()), round(p.y()))


def _named(win, name):
    todo = [win.contentItem()]
    while todo:
        it = todo.pop()
        if it.objectName() == name and it.isVisible():
            return it
        todo.extend(it.childItems())
    raise AssertionError(f"no visible {name}")


def _drag(win, a, by):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QGuiApplication, QMouseEvent
    from PySide6.QtTest import QTest
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
    for i in range(1, 9):
        q = QPointF(a + by * i / 8)
        QGuiApplication.sendEvent(win, QMouseEvent(QEvent.MouseMove, q, win.mapToGlobal(q), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.qWait(16)
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, a + by)
    QTest.qWait(200)


def test_click_after_undo_copies_the_layer(screen):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    b, win = screen
    _drag(win, _middle(win, b, "a"), QPoint(60, 40))
    QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
    QTest.qWait(250)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, _middle(win, b, "a"))     # its x key's square lies right there
    QTest.qWait(200)
    QTest.keyClick(win, Qt.Key_C, Qt.ControlModifier)
    QTest.qWait(100)
    assert b._keys.about == "layers" and list(b.selection) == ["a"]
    assert b.status.startswith("Copied 1 layer"), b.status


def test_right_moves_two_picked_keys_one_frame_one_step(screen):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    b, win = screen
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, _middle(win, b, "a"))
    QTest.qWait(300)
    for name, mods in (("keyDot:a.x.k0", Qt.NoModifier), ("keyDot:a.x.k2000", Qt.ControlModifier)):
        dot = _named(win, name)
        p = dot.mapToScene(QPointF(dot.width() / 2, dot.height() / 2)).toPoint()
        QTest.mouseClick(win, Qt.LeftButton, mods, p)
        QTest.qWait(150)
    assert b._keys.about == "keys" and len(b._keys.ids) == 2
    steps = len(b.doc.history.changes)
    QTest.keyClick(win, Qt.Key_Right, Qt.NoModifier)
    QTest.qWait(150)
    times = sorted(round(k["t"], 4) for k in b.doc.item("a")["keys"])
    assert times == [round(1 / 30, 4), round(2 + 1 / 30, 4)]
    assert len(b.doc.history.changes) == steps + 1
