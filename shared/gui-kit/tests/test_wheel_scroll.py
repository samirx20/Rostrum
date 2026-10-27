"""The wheel always scrolls a long panel to its end unless the box under the pointer has the caret in it (3D brief 22's
kit ask: the settings panel stopped at about half, a number box or slider that kept the keyboard after a click, a
scrub or a drag took the wheel once the panel had scrolled it under the pointer). Real wheel events into a real window."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QUrl, Qt
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtQuick import QQuickView

KIT = Path(__file__).resolve().parents[1] / "qml"
SCENE = """
import QtQuick
import RostrumKit
Item {
    width: 400; height: 300
    Flickable {
        id: scroller; objectName: "scroll"; anchors.fill: parent; clip: true
        contentHeight: col.height; boundsBehavior: Flickable.StopAtBounds
        WheelScroll { flick: scroller }
        Column {
            id: col; width: parent.width
            Repeater {
                model: 20
                Row {
                    id: row; required property int index; height: 40; spacing: 10
                    NumberField { objectName: "num" + row.index; width: 150; from: 0; to: 100; value: 50
                                  onEdited: (v) => value = v }
                    Slider { objectName: "slide" + row.index; width: 150; from: 0; to: 100; step: 1; value: 50
                             onEdited: (v) => value = v; onScrubbed: (v) => value = v }
                }
            }
        }
    }
}
"""


def _find(root, name):
    todo = [root]
    while todo:
        o = todo.pop()
        if o.objectName() == name:
            return o
        todo.extend(o.childItems())


def _scene(tmp_path):
    from PySide6.QtTest import QTest
    QGuiApplication.instance() or QGuiApplication([])
    win = QQuickView()
    win.engine().addImportPath(str(KIT))
    win.rootContext().setContextProperty("uiFont", "Segoe UI")
    qml = tmp_path / "scene.qml"
    qml.write_text(SCENE, encoding="utf-8")
    win.setSource(QUrl.fromLocalFile(str(qml)))
    win.show()
    QTest.qWaitForWindowExposed(win)
    QTest.qWait(100)
    return win, _find(win.contentItem(), "scroll")


def _wheel(win, at, notches):
    from PySide6.QtTest import QTest
    for _ in range(abs(notches)):
        ev = QWheelEvent(QPointF(at), QPointF(win.mapToGlobal(at)), QPoint(), QPoint(0, 120 if notches > 0 else -120),
                         Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        QGuiApplication.sendEvent(win, ev)
        QTest.qWait(15)


def _click(win, item, x=8, y=8):
    from PySide6.QtTest import QTest
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, item.mapToScene(QPointF(x, y)).toPoint())


def _end(sc):
    return sc.property("contentHeight") - sc.height()


def test_the_wheel_reaches_the_end_of_a_long_panel(tmp_path):
    win, sc = _scene(tmp_path)
    _wheel(win, QPoint(40, 150), -40)
    assert sc.property("contentY") == _end(sc) > 400


def test_a_box_or_slider_that_kept_the_keyboard_never_stops_the_panel(tmp_path):
    win, sc = _scene(tmp_path)
    for name, x in (("num7", 40), ("slide7", 250)):     # clicked once (caret in / pressed), then the pointer waits above it
        sc.setProperty("contentY", 110)                 # 70 px below the pointer: the first notch (3 rows, 84 px) scrolls it under
        _click(win, _find(sc, name))
        kept = _find(sc, name)
        assert kept.property("activeFocus") or kept.property("input").property("activeFocus")
        before = _find(sc, name).property("value")      # (a press on a slider jumps it to the pointer)
        _wheel(win, QPoint(x, 100), -45)                # the panel scrolls it up under the pointer, and on to the end
        assert sc.property("contentY") == _end(sc), name
        assert _find(sc, name).property("value") == before, name      # none of the notches changed it
        sc.setProperty("contentY", 0)


def test_a_box_with_the_caret_in_it_still_takes_the_wheel(tmp_path):
    win, sc = _scene(tmp_path)
    box = _find(sc, "num1")
    _click(win, box)
    _wheel(win, box.mapToScene(QPointF(30, 20)).toPoint(), 2)
    assert box.property("value") == 52 and sc.property("contentY") == 0


def test_a_slider_the_keyboard_stepped_to_still_takes_the_wheel(tmp_path):
    win, sc = _scene(tmp_path)
    s = _find(sc, "slide0")
    s.forceActiveFocus(Qt.TabFocusReason)
    _wheel(win, s.mapToScene(QPointF(60, 20)).toPoint(), 3)
    assert s.property("value") == 53 and sc.property("contentY") == 0
