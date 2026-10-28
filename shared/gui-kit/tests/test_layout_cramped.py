"""The layout check flags a popup's list squeezed to a sliver at the window's edge (the 3D sweep's eye Material list:
two rows shown, Glossy plastic unreachable, 0 faults reported) and passes the same list given its room."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QUrl

SCENE = """import QtQuick
Item { width: 400; height: 900
  Rectangle { z: 20; x: 20; y: 900 - %d - 10 + %d; width: 300; height: %d; color: "#333"
    Flickable { anchors.fill: parent; clip: true; contentHeight: 600; contentWidth: width
      Column { width: parent.width
        Repeater { model: 20; Rectangle { width: 300; height: 30; color: index %% 2 ? "#444" : "#555" } } } } } }"""


def kinds(tmp_path, height: int, down: int = 0) -> list[str]:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
    from rostrum_gui import layout_check
    QGuiApplication.instance() or QGuiApplication([])
    f = tmp_path / "Scene.qml"
    f.write_text(SCENE % (height, down, height), encoding="utf-8")
    v = QQuickView()
    v.setSource(QUrl.fromLocalFile(str(f)))
    v.show()
    QTest.qWaitForWindowExposed(v)
    found = [x.kind for x in layout_check.check(v)]
    v.close()
    v.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return found


def test_a_popup_list_squeezed_to_a_sliver_is_a_fault(tmp_path):
    assert "cramped" in kinds(tmp_path, 120)


def test_a_popup_list_given_its_room_passes(tmp_path):
    assert "cramped" not in kinds(tmp_path, 500)


def test_a_popup_list_running_off_the_window_is_outside(tmp_path):
    assert "outside" in kinds(tmp_path, 500, down=200)
