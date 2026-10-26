"""A 15 px dot at Fit: Alt+drag from its middle copies it, never stretches it (critic r8, must-fix 6). The resize squares of a
small box sit outside it (Handles.qml), so the body wins. Real mouse into the real window."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SRC = '''
comp("c", width=1920, height=1080, fps=10, duration=4)
shape("dot", w=28, h=28, x=500, y=500, fill="#ff5533", shape="ellipse")
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


def test_alt_drag_from_the_middle_of_a_tiny_dot_copies_it(screen):
    from PySide6.QtCore import QObject, QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    b, win = screen
    st = win.findChild(QObject, "stage")
    scale = st.property("compScale")
    o = st.property("compOrigin")
    q = st.mapToScene(QPointF(o.x() + 500 * scale, o.y() + 500 * scale))
    c = QPoint(round(q.x()), round(q.y()))
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, c)
    QTest.qWait(300)
    QTest.mouseMove(win, c)
    QTest.mousePress(win, Qt.LeftButton, Qt.AltModifier, c)
    for i in range(1, 9):
        QTest.mouseMove(win, c + QPoint(8 * i, 4 * i))
        QTest.qWait(16)
    QTest.mouseRelease(win, Qt.LeftButton, Qt.AltModifier, c + QPoint(64, 32))
    QTest.qWait(300)
    layers = {l["id"]: l for l in b.comp()["layers"]}
    assert (round(layers["dot"]["x"]), round(layers["dot"]["w"])) == (500, 28), "the original must stay as it was"
    copies = [l for i, l in layers.items() if i not in ("dot", "frame")]
    assert len(copies) == 1 and round(copies[0]["w"]) == 28 and copies[0]["x"] > 560
