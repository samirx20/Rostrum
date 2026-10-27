"""The critic's feel tools see what a person sees: the first frame after a press shows the press, and the picture strip
finds a stretch where the screen froze before it changed again."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt, QUrl

SCENE = b"""import QtQuick
Rectangle { width: 200; height: 120; property int phase: 0
  color: area.pressed ? "red" : ["blue", "green", "yellow"][phase]
  Timer { id: later; interval: 400; onTriggered: phase = 2 }
  MouseArea { id: area; anchors.fill: parent; onClicked: { phase = 1; later.start() } } }"""


def view(tmp_path):
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
    QGuiApplication.instance() or QGuiApplication([])
    f = tmp_path / "Feel.qml"
    f.write_bytes(SCENE)
    v = QQuickView()
    v.setSource(QUrl.fromLocalFile(str(f)))
    v.show()
    QTest.qWaitForWindowExposed(v)
    return v


def close(v):
    v.close()
    v.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_first_frame_shows_the_press(tmp_path):
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest
    from rostrum_gui import feel
    v = view(tmp_path)
    shot = feel.first_frame(v, lambda: QTest.mousePress(v, Qt.LeftButton, Qt.NoModifier, QPoint(50, 50)))
    QTest.mouseRelease(v, Qt.LeftButton, Qt.NoModifier, QPoint(50, 50))
    close(v)
    assert shot.image.pixelColor(50, 50) == QColor("red"), shot.image.pixelColor(50, 50).name()


def test_strip_finds_the_frozen_gap(tmp_path):
    from PySide6.QtTest import QTest
    from rostrum_gui import feel
    v = view(tmp_path)
    s = feel.strip(v, lambda: QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(50, 50)), ms=700)
    close(v)
    gaps = feel.frozen_gaps(s)
    assert s.first_change_ms is not None and s.first_change_ms < 150, (s.times, s.changed)
    assert gaps and gaps[0][1] - gaps[0][0] >= 250 and gaps[0][1] >= 380, (gaps, s.times, s.changed)
    assert os.path.isfile(feel.contact_sheet(s, tmp_path / "strip.png"))
