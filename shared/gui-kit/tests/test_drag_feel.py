"""Drag feel (INTERACTION.md 1.22): a real Esc key during a drag cancels it, before anything else in the window hears
it, and leaves no step; after the drag Esc is the window's again. The value chip sits below-right of the pointer,
flips at the edge, says what a held key does, and lingers 600 ms after the drag."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest

from rostrum_gui.drag import Mods, PointerDrag, hint_of
from rostrum_gui.pointer import wait

KIT = Path(__file__).resolve().parents[1] / "qml"
SCENE = """
import QtQuick
import QtQuick.Window
import RostrumKit
Window {
    width: 400; height: 300; visible: true
    property int escs: 0
    Item { anchors.fill: parent; focus: true; Keys.onEscapePressed: escs++ }
    DragLabel { id: chip; objectName: "chip" }
}
"""


class Drag:
    def __init__(self):
        self.ended = None

    def preview(self, calls):
        pass

    def end(self, cancel=False):
        self.ended = "cancel" if cancel else "kept"
        return None if cancel else "change"


def _window(tmp_path):
    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(KIT))
    engine.rootContext().setContextProperty("uiFont", "Segoe UI")
    qml = tmp_path / "scene.qml"
    qml.write_text(SCENE, encoding="utf-8")
    engine.load(QUrl.fromLocalFile(str(qml)))
    win = engine.rootObjects()[0]
    wait(50)
    return app, engine, win


def _close(win, engine):
    win.close(); win.deleteLater(); engine.deleteLater(); wait(30)    # gone, so no later window waits on it


def test_esc_cancels_the_drag_first_and_is_the_windows_after(tmp_path):
    app, engine, win = _window(tmp_path)
    doc = Drag()
    d = PointerDrag(10, 10, lambda: doc)
    assert d.move(30, 10)                          # past 4 px: a drag
    QTest.keyClick(win, Qt.Key_Escape)
    assert doc.ended == "cancel" and d.state == "cancelled" and win.property("escs") == 0
    assert d.release() is None                     # the release after a cancel records nothing
    QTest.keyClick(win, Qt.Key_Escape)
    assert win.property("escs") == 1               # no drag: Esc is the window's own again
    d2 = PointerDrag(0, 0, lambda: Drag())
    d2.move(20, 0)
    assert d2.release() == "change" and d2.grabbed(5, 5) == (25, 5)
    QTest.keyClick(win, Qt.Key_Escape)
    assert win.property("escs") == 2               # a released drag lets Esc go
    _close(win, engine)


def test_value_chip_places_flips_and_lingers(tmp_path):
    app, engine, win = _window(tmp_path)
    chip = win.findChild(QObject, "chip")
    chip.setProperty("text", "35°")
    chip.setProperty("hint", hint_of(Mods(straight=True), "turn"))
    chip.setProperty("at", QPointF(100, 100))
    wait(20)
    assert chip.property("visible") and chip.property("x") == 116 and chip.property("y") == 116
    chip.setProperty("at", QPointF(395, 100))             # near the right edge: it goes to the left of the pointer
    wait(20)
    assert chip.property("x") + chip.property("width") <= 395 - 16 + 0.5
    chip.setProperty("text", "")                   # the drag ended: the last words stay 600 ms, then go
    wait(200)
    assert chip.property("visible") and chip.property("shownText") == "35°"
    wait(600)
    assert not chip.property("visible")
    assert hint_of(Mods(straight=True, copy=True), "resize") == "keep ratio · from centre"
    _close(win, engine)


def test_a_qml_drag_owns_esc_and_beats_read_plainly(tmp_path):
    from rostrum_gui.drag import words_beats
    from rostrum_gui.drag_esc import ESC
    app, engine, win = _window(tmp_path)
    got = []
    ESC.cancelled.connect(lambda: got.append(1))
    ESC.holdEsc()                                  # a QML drag started (dragEsc.holdEsc())
    QTest.keyClick(win, Qt.Key_Escape)
    assert got == [1] and win.property("escs") == 0
    QTest.keyClick(win, Qt.Key_Escape)             # cancelled: Esc is the window's again
    assert got == [1] and win.property("escs") == 1
    ESC.holdEsc(); ESC.letEsc()                    # a drag that ended lets Esc go
    QTest.keyClick(win, Qt.Key_Escape)
    assert win.property("escs") == 2
    assert [words_beats(6), words_beats(-3), words_beats(0.5)] == ["+1 bar 2 beats", "−3 beats", "+½ beat"]
    _close(win, engine)


def test_qml_sees_hold_esc_and_let_esc_as_slots():
    """DRAG.md tells QML to call dragEsc.holdEsc() / letEsc(): they must be slots QML can see, not Python aliases."""
    from rostrum_gui.drag_esc import ESC
    mo = ESC.metaObject()
    names = {bytes(mo.method(i).name()).decode() for i in range(mo.methodCount())}
    assert {"holdEsc", "letEsc"} <= names
