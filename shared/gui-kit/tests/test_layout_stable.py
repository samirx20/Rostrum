"""The stability pass fails a click that pushes the controls above it (a row appearing over the pointer, the bug behind
every wrong-row click in the critic rounds) and passes one whose new row appears below. The lowest control is
clicked first ("Grow"); the button above it is what must stay put."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QUrl

SCENE = """import QtQuick
Item { width: 600; height: 500; property bool grown: false
  Rectangle { x: 20; y: 20; width: 300; height: 400; clip: true; color: "#333"
    Column { width: parent.width; spacing: 6
      %s
      Rectangle { objectName: "other"; width: 120; height: 30; color: "#555"; MouseArea { anchors.fill: parent } }
      Rectangle { objectName: "grow"; width: 120; height: 30; color: "#666"
                  Text { anchors.centerIn: parent; text: "Grow" }
                  MouseArea { anchors.fill: parent; onClicked: grown = true } }
      %s } } }"""
ROW = 'Rectangle { visible: grown; width: 200; height: 36; color: "#a33" }'


def run(tmp_path, above: bool) -> list[str]:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
    from rostrum_gui import layout_stable, pointer
    QGuiApplication.instance() or QGuiApplication([])
    f = tmp_path / "Scene.qml"
    f.write_text(SCENE % ((ROW, "") if above else ("", ROW)), encoding="utf-8")
    v = QQuickView()
    v.setSource(QUrl.fromLocalFile(str(f)))
    v.show()
    QTest.qWaitForWindowExposed(v)
    pointer.wait(50)
    lines = layout_stable.run_state(v, tmp_path, "scene", restore=None)
    v.close()
    v.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return lines


def test_a_row_inserted_above_the_clicked_button_fails(tmp_path):
    lines = run(tmp_path, above=True)
    assert len(lines) == 1 and "grow" in lines[0] and "(above)" in lines[0] and "(itself)" in lines[0], lines
    assert (tmp_path / "scene-stable-1.png").is_file()


def test_a_row_inserted_below_passes(tmp_path):
    assert run(tmp_path, above=False) == []
    assert '"clicked": 2' in (tmp_path / "stable.json").read_text(encoding="utf-8")
