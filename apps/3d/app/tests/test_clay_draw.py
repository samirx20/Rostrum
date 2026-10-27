"""Clay's Draw (clay_draw_qt.py, ClayDraw.qml), by real mouse input on the drawn layer: what would break silently is an
outline drawn on the picture landing as points off one plane (a twisted or flattened shape), the plane not standing on
the ground under the outline, a drag making more than one change, and Esc mid-drag leaving something behind. No engine:
its pick answers "nothing here" (the ground rule); the operation is recorded, not run."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest  # noqa: E402
from PySide6.QtCore import QObject, QPoint, QUrl, Qt, Signal  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from rostrum_gui import cursor_item  # noqa: E402,F401  registers CanvasCursor
from rostrum_gui.app import KIT_QML  # noqa: E402
from screen3d import esc3d  # noqa: E402
from screen3d.clay_draw_qt import ClayDraw  # noqa: E402

CAM = {"eye": [0.0, 1.0, 3.0], "target": [0.0, 0.4, 0.0], "fov": 40.0, "frame": 0, "width": 800, "height": 600}
WINDOW = '''
import QtQuick
import QtQuick.Window
Window { width: 800; height: 600; visible: true
         ClayDraw { objectName: "draw"; anchors.fill: parent; d: drawer } }
'''


class Tool(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.calls, self.fails = [], []
        doc = SimpleNamespace(has=lambda i: False, item=lambda i: {})
        self.b = SimpleNamespace(doc=doc, _guard=lambda fn: fn() or True, fail_line=self.fails.append,
                                 _apply=lambda calls, label: self.calls.append((calls, label)),
                                 select=lambda i: None, label_of=lambda it: "")
        eng = SimpleNamespace(ensure_scene=lambda s: True, pick=lambda **req: {"hit": False})
        self.v = SimpleNamespace(_size=(800, 600), _scale=1.0, sent=lambda: ({}, dict(CAM)), redraw=lambda: None,
                                 _r=SimpleNamespace(call=lambda job: job(eng)))
        self.draws, self.tool = True, "draw"

    def _all_clays(self):
        return []


@pytest.fixture
def drawing():
    app = QGuiApplication.instance() or QGuiApplication([])
    tool = Tool()
    drawer = ClayDraw(tool)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(KIT_QML))
    engine.rootContext().setContextProperty("drawer", drawer)
    engine.rootContext().setContextProperty("uiFont", "Segoe UI")
    engine.loadData(WINDOW.encode(), QUrl.fromLocalFile(str(APP / "qml" / "_test_clay_draw.qml")))
    assert engine.rootObjects(), "ClayDraw.qml did not load"
    win = engine.rootObjects()[0]
    QTest.qWaitForWindowExposed(win)
    yield win, tool, drawer
    win.close()
    del engine
    app.processEvents()


def _drag(win, pts):
    """A real press, moves and (unless the caller ends it) the moves only; returns the last point."""
    QTest.mouseMove(win, pts[0])
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, pts[0])
    for p in pts[1:]:
        QTest.mouseMove(win, p)
    return pts[-1]


def _pear(cx=400, cy=330, rx=60, ry=110, n=40):
    import math
    return [QPoint(round(cx + rx * (0.7 + 0.3 * math.sin(t)) * math.cos(t)), round(cy - ry * math.sin(t)))
            for t in (2 * math.pi * i / n for i in range(n + 1))]


def test_a_drawn_outline_is_one_new_clay_on_one_upright_plane_on_the_ground(drawing):
    win, tool, drawer = drawing
    pts = _pear()
    last = _drag(win, pts)
    assert drawer.chip.endswith("cm"), drawer.chip                       # the size while drawing
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, last)
    QTest.qWait(10)
    assert not tool.fails, tool.fails
    assert len(tool.calls) == 1 and len(tool.calls[0][0]) == 1           # one change, one operation
    call = tool.calls[0][0][0]
    assert call["op"] == "clay.add" and call["target"] == []
    outline, n = call["args"]["draw"], call["args"]["facing"]
    assert len(outline) > 20
    assert abs(n[1]) < 1e-9 and n[2] > 0.99                              # upright, facing the camera (at +z)
    p0 = outline[0]
    assert max(abs(sum((p[k] - p0[k]) * n[k] for k in range(3))) for p in outline) < 1e-3       # one plane
    assert min(p[1] for p in outline) == pytest.approx(0.0, abs=2e-3)   # standing on the ground under its lowest pixel
    assert drawer.line == [] and drawer.chip == ""


def test_esc_mid_drag_drops_the_outline_and_changes_nothing(drawing):
    win, tool, drawer = drawing
    last = _drag(win, _pear())
    assert len(drawer.line) > 20
    b = SimpleNamespace(viewport=SimpleNamespace(gizmo=SimpleNamespace(dragging=False),
                                                 clay_tool=SimpleNamespace(_phase="", drawer=drawer)))
    assert esc3d.step(b) == "draw"
    assert drawer.line == [] and not drawer.drawing
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, last)
    QTest.qWait(10)
    assert tool.calls == [] and tool.fails == []
