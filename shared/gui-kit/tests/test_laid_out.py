"""A scripted click right after a click that changed the layout lands where the controls are now, though the window
drew no frame in between (laid_out.py; the bug: a check clicked a row's old place in a window that drew nothing)."""
import os

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtTest import QTest

QML = b"""import QtQuick; import QtQuick.Layouts
ColumnLayout { width: 200; height: 300; spacing: 0; property string hit: ""
  Rectangle { id: a; Layout.preferredHeight: 100; Layout.fillWidth: true
              MouseArea { anchors.fill: parent; onClicked: { parent.parent.hit += "a"; a.visible = false } } }
  Rectangle { Layout.preferredHeight: 100; Layout.fillWidth: true
              MouseArea { anchors.fill: parent; onClicked: parent.parent.hit += "b" } }
  Item { Layout.fillHeight: true } }"""


def test_a_click_after_a_layout_change_lands_on_the_new_layout(tmp_path):
    from PySide6.QtQuick import QQuickView
    from rostrum_gui.app import qt_app
    from rostrum_gui.laid_out import watch
    qt_app()
    f = tmp_path / "Rows.qml"
    f.write_bytes(QML)
    v = QQuickView()
    v.setSource(QUrl.fromLocalFile(str(f)))
    v.show()
    QTest.qWaitForWindowExposed(v)
    watch(v)
    at = QPoint(100, 50)
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, at)      # hides the first row: the second moves up under `at`
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, at)      # no frame drawn in between
    assert v.rootObject().property("hit") == "ab"
    v.close()
