"""A tip never takes a click (HoverTipLine.qml): a number box's "Type a number" line, shown after a letter and still up
over the row below, let a click on that row's box miss (2D: Size → Opacity, Taper start → Taper end)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

KIT_QML = Path(__file__).resolve().parents[1] / "qml"
ROWS = b"""
import QtQuick
import RostrumKit
Window { width: 300; height: 200; visible: true
  property bool lowerTyping: lower.input.activeFocus
  property bool tipUp: upper.children.length > 0 && tipShown()
  function tipShown() { for (const c of upper.data) if (c.shown !== undefined) return c.shown; return false }
  Column { x: 20; y: 20; spacing: 4
    NumberField { id: upper; objectName: "upper"; width: 120; value: 5 }
    NumberField { id: lower; objectName: "lower"; width: 120; value: 7 } } }
"""


def _centre(item):
    p = item.mapToScene(item.boundingRect().center())
    return QPoint(int(p.x()), int(p.y()))


def test_a_letter_tip_never_takes_the_next_rows_click():
    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(KIT_QML))
    for name, value in (("uiFont", "Arial"), ("monoFont", "Consolas")):
        engine.rootContext().setContextProperty(name, value)
    engine.loadData(ROWS, QUrl.fromLocalFile(str(KIT_QML / "tip_test.qml")))
    win = engine.rootObjects()[0]
    win.requestActivate()
    QTest.qWait(100)
    upper, lower = win.findChild(QQuickItem, "upper"), win.findChild(QQuickItem, "lower")
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _centre(upper))
    QTest.qWait(300)
    QTest.keyClick(win, Qt.Key.Key_Q)       # a letter: the box says "Type a number, like 12 or +5" under itself
    QTest.qWait(100)
    assert win.property("tipUp"), "the letter's tip did not show"
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _centre(lower))
    QTest.qWait(300)
    assert win.property("lowerTyping"), "the click on the row below went to the tip"
    win.close()
    app.processEvents()
