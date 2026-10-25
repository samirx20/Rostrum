"""Press an eye on a layer row and drag down over more rows: every row passed takes the first row's new state and it is
ONE change, so one Ctrl+Z shows them all again (a swipe that made one step per row would leave half undone). Real mouse
and key events on the eye a person sees. Needs the built engine."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

LAYERS = "\n".join(f'shape("r{i}", w=100, h=60, fill="#336699", x={100 + i * 120}, y=200)' for i in range(5))


def test_eye_drag_hides_every_row_passed_in_one_step(tmp_path):
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QGuiApplication, QMouseEvent
    from PySide6.QtTest import QTest
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source('comp("main", name="Main", width=1920, height=1080, fps=30, duration=4)\n' + LAYERS, "a.py"))
    session.files.put(doc)
    QTest.qWait(1500)
    b, win = session.bridge, session.win
    ids = [r["id"] for r in b.layers if r["row"] == "layer" and not r.get("frame")][:4]
    assert len(ids) == 4
    hidden = lambda: [i for i in ids if b.doc.item(i).get("hidden")]   # noqa: E731

    def named(name):                                                      # the visual tree: rows are items, not QObject children
        todo = [win.contentItem()]
        while todo:
            o = todo.pop()
            if o.objectName() == name:
                return o
            todo.extend(o.childItems())

    point = lambda i: named(f"layerSwitch:{i}:hidden").mapToScene(QPointF(9, 9)).toPoint()   # noqa: E731
    try:
        win.grabWindow()
        QTest.mouseMove(win, QPoint(100, int(point(ids[0]).y())))        # point at row 1: its eye shows
        QTest.qWait(250)
        win.grabWindow()
        a, last = point(ids[0]), point(ids[3])
        QTest.mouseMove(win, a)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
        for n in range(1, 11):                                            # drag down over rows 2 to 4
            q = QPointF(a.x(), a.y() + (last.y() - a.y()) * n / 10)
            QGuiApplication.sendEvent(win, QMouseEvent(QEvent.MouseMove, q, win.mapToGlobal(q), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            QTest.qWait(16)
        assert hidden() == []                                             # live only on the screen until release
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, last)
        QTest.qWait(200)
        assert hidden() == ids
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(200)
        assert hidden() == []                                             # one Ctrl+Z: all four back
    finally:
        app.processEvents()
        session.close()
