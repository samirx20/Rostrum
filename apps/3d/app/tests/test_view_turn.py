"""Turning the view in every tool (TurnArea.qml, screen3d/view_input.py), by real mouse input: a right drag must turn the
view and never open the menu, a right click (no drag) must still open it, and a mouse wheel must zoom while a touchpad's
two-finger scroll turns. Each would break silently (a menu on every turn, or no menu at all)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest  # noqa: E402
from PySide6.QtCore import QPoint, QUrl, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from screen3d import view_input  # noqa: E402

WINDOW = '''
import QtQuick
import QtQuick.Window
Window { width: 400; height: 300; visible: true
         property var turns: []
         property var clicks: []
         TurnArea { anchors.fill: parent
                    onTurned: (dx, dy) => turns = turns.concat([[dx, dy]])
                    onRightClicked: (x, y) => clicks = clicks.concat([[x, y]]) } }
'''


@pytest.fixture
def win():
    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    engine.loadData(WINDOW.encode(), QUrl.fromLocalFile(str(APP / "qml" / "_test_view_turn.qml")))
    assert engine.rootObjects(), "TurnArea.qml did not load"
    w = engine.rootObjects()[0]
    QTest.qWaitForWindowExposed(w)
    yield w
    w.close()
    del engine
    app.processEvents()


def got(win, name) -> list:
    return [list(v) for v in win.property(name).toVariant()]


def test_right_click_opens_the_menu_and_right_drag_turns(win):
    QTest.mouseMove(win, QPoint(100, 100))
    QTest.mousePress(win, Qt.RightButton, Qt.NoModifier, QPoint(100, 100))
    QTest.mouseMove(win, QPoint(102, 101))                # a hand's wobble is still a click
    QTest.mouseRelease(win, Qt.RightButton, Qt.NoModifier, QPoint(102, 101))
    assert got(win, "clicks") == [[100, 100]] and got(win, "turns") == []
    QTest.mousePress(win, Qt.RightButton, Qt.NoModifier, QPoint(100, 100))
    for x in (110, 130, 160):
        QTest.mouseMove(win, QPoint(x, 120))
    QTest.mouseRelease(win, Qt.RightButton, Qt.NoModifier, QPoint(160, 120))
    turns = got(win, "turns")
    assert sum(t[0] for t in turns) == 60 and sum(t[1] for t in turns) == 20
    assert len(got(win, "clicks")) == 1                    # no menu after a turn


def test_wheel_zooms_and_a_touchpad_turns():
    assert view_input.wheel(0, 120, 0, 0, False, False, False) == ("zoom", 1.0, 0.0)          # a mouse notch
    assert view_input.wheel(0, 18, 0, 0, False, True, False)[0] == "zoom"                     # Windows' pinch: Ctrl + wheel
    assert view_input.wheel(-8, 24, 0, 0, False, False, False) == ("orbit", -2.0, 6.0)        # Windows precision touchpad
    assert view_input.wheel(0, 120, 3, 9, True, False, False) == ("orbit", 3.0, 9.0)         # macOS: pixels and a phase
    assert view_input.wheel(0, 120, 0, 0, False, False, True)[0] == "orbit"                   # the device says touchpad
    assert view_input.pinch_steps(1.0) == 0 and view_input.pinch_steps(1.5) > 0
