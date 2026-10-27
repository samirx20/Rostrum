"""A colour picked with the picker's square stays when the picker closes: by a click away, by the window's Esc and by
Enter in its hex box. The hex box takes the keys from the open (typed hexes never hit the canvas), and it used to keep
the old colour's text: its focus loss at the close sent that back, undoing the pick (3D CL7b's grey eye)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

KIT = Path(__file__).resolve().parents[1] / "qml"
SCENE = """
import QtQuick
import RostrumKit
Item {
    width: 900; height: 600
    ColorField { objectName: "cf"; x: 600; y: 40; width: 200; hex: "#b3b3b3"; onEdited: (v) => hex = v }
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
    win.rootContext().setContextProperty("monoFont", "Consolas")
    qml = tmp_path / "scene.qml"
    qml.write_text(SCENE, encoding="utf-8")
    win.setSource(QUrl.fromLocalFile(str(qml)))
    win.show()
    QTest.qWaitForWindowExposed(win)
    QTest.qWait(100)
    return win


def _input(field):
    todo = [field]
    while todo:
        o = todo.pop()
        if o.inherits("QQuickTextInput"):
            return o
        todo.extend(o.childItems())


def _at(win, item, x, y):
    return item.mapToScene(QPointF(x, y)).toPoint()


@pytest.mark.parametrize("close", ["click away", "esc", "enter"])
def test_a_colour_picked_in_the_square_stays_after_the_close(tmp_path, close):
    from PySide6.QtTest import QTest
    win = _scene(tmp_path)
    cf = _find(win.contentItem(), "cf")
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, _at(win, _find(cf, "swatch"), 6, 6))
    QTest.qWait(150)
    sq = _find(win.contentItem(), "colourSquare")
    assert sq is not None and sq.isVisible()
    hexin = _input(_find(sq.parentItem(), "hexField"))
    assert hexin.hasActiveFocus()                 # the hex box has the keys, holding the old colour, all selected
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, _at(win, sq, 4, sq.height() - 2))    # bottom: (near) black
    QTest.qWait(50)
    picked = cf.property("hex")
    assert picked != "#b3b3b3" and int(picked[1:3], 16) < 0x10
    if close == "click away":
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, _at(win, win.contentItem(), 20, 580))
    elif close == "esc":                                  # the window's one Esc (OpenPopups) closes the popup itself
        popup = _find(win.contentItem(), "colourSquare")
        while popup is not None and not popup.inherits("QQuickPopupItem"):
            popup = popup.parentItem()
        from PySide6.QtCore import QMetaObject
        QMetaObject.invokeMethod(popup.parent(), "close")     # (no AppShell here: OpenPopups.top.close(), as that Esc does)
    else:
        QTest.keyClick(win, Qt.Key_Return)
    QTest.qWait(150)
    assert cf.property("hex") == picked, close


def test_a_hex_typed_after_the_open_still_lands(tmp_path):
    from PySide6.QtTest import QTest
    win = _scene(tmp_path)
    cf = _find(win.contentItem(), "cf")
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, _at(win, _find(cf, "swatch"), 6, 6))
    QTest.qWait(150)
    for c in "FF4A9C":
        QTest.keyClick(win, getattr(Qt, f"Key_{c}"))
    QTest.keyClick(win, Qt.Key_Return)
    QTest.qWait(100)
    assert cf.property("hex").lower() == "#ff4a9c"
