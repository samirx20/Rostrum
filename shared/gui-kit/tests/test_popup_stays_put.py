"""A menu is sized and placed before it shows and never moves while visible: it moved a moment after opening (its rows were
measured once built) and a click landed on another row than the one under the pointer. Its first size is its last."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QMetaObject, Q_ARG, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtQml import QQmlApplicationEngine

from rostrum_gui.app import stop

KIT_QML = Path(__file__).resolve().parents[1] / "qml"
WINDOW = b"""
import QtQuick
import QtQuick.Window
import RostrumKit
Window { width: 900; height: 700; visible: true
         property var entries: []
         readonly property var geometry: [menu.x, menu.y, menu.width, menu.height, menu.visible]
         function show(px, py) { menu.entries = entries; menu.openAt(px, py) }
         function hide() { menu.close() }
         ActionMenu { id: menu } }
"""
ENTRIES = [{"value": "a", "label": "Make a chord", "group": "x", "sub": [{"value": "a1", "label": "In key", "group": "x"}]},
           {"value": "b", "label": "Invert up", "keys": "Alt+Up", "group": "y"},
           {"value": "c", "label": "Strum…", "group": "z", "heading": "Shape"}, {"value": "d", "label": "Arpeggio…", "group": "z"}]


def test_a_menu_does_not_move_after_it_shows():
    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(KIT_QML))
    for name, value in (("uiFont", "Arial"), ("monoFont", "Consolas")):
        engine.rootContext().setContextProperty(name, value)
    engine.loadData(WINDOW, QUrl.fromLocalFile(str(KIT_QML / "popup_test.qml")))
    window = engine.rootObjects()[0]
    window.setProperty("entries", ENTRIES)
    app.processEvents()
    for px, py in ((100, 100), (850, 650)):                 # in the open, and near the window's far corner (it flips)
        QMetaObject.invokeMethod(window, "show", Qt.DirectConnection, Q_ARG("QVariant", px), Q_ARG("QVariant", py))
        first = window.property("geometry").toVariant()
        assert first[4], "the menu is visible as soon as it opens"
        QTest.qWait(300)
        assert window.property("geometry").toVariant() == first, "the menu moved or changed size after it showed"
        QMetaObject.invokeMethod(window, "hide", Qt.DirectConnection)
        QTest.qWait(300)
    stop(engine, window)
