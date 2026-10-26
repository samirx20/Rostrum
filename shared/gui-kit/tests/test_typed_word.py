"""A word typed with no box focused runs no commands (Sound critic r9 + r10: typing "drums" added a marker from its M
and put the S into the marker's name). A lone command key still runs, and a text field still gets every letter."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from rostrum_gui import typed_word  # noqa: E402

WINDOW = b"""
import QtQuick
import QtQuick.Window
Window { width: 300; height: 200; visible: true
    property int marks: 0
    property alias text: field.text
    Shortcut { sequence: "M"; context: Qt.ApplicationShortcut; onActivated: marks++ }
    TextInput { id: field; objectName: "field"; width: 200; height: 30; selectByMouse: true }
}
"""


def test_a_word_runs_no_command_but_a_lone_key_and_a_field_do():
    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    engine.loadData(WINDOW)
    win = engine.rootObjects()[0]
    now = [100.0]
    typed_word.TypedWord(win, clock=lambda: now[0])
    QTest.qWait(50)
    win.contentItem().forceActiveFocus()

    def key(k, after):
        now[0] += after
        QTest.keyClick(win, k)

    key(Qt.Key_M, 1.0)
    assert win.property("marks") == 1, "a lone M (a command key) did nothing"
    for k in (Qt.Key_D, Qt.Key_R, Qt.Key_U, Qt.Key_M, Qt.Key_S):     # "drums", typed
        key(k, 0.08 if k != Qt.Key_D else 1.0)
    assert win.property("marks") == 1, "the M inside a typed word ran its command"
    key(Qt.Key_M, 1.0)
    assert win.property("marks") == 2, "a lone M after the word did nothing"

    from PySide6.QtCore import QCoreApplication, QEvent  # a press sent straight to the window (a script's)
    from PySide6.QtGui import QKeyEvent
    for k, ch in ((Qt.Key_D, "d"), (Qt.Key_M, "m")):
        now[0] += 0.05
        QCoreApplication.sendEvent(win, QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier, ch))
    assert win.property("marks") == 2, "an M sent straight to the window inside a word ran its command"

    win.findChild(object, "field").forceActiveFocus()
    for k in (Qt.Key_M, Qt.Key_I, Qt.Key_X):
        key(k, 0.05)
    assert win.property("text") == "mix" and win.property("marks") == 2, "a text field lost letters to the guard"
    engine.deleteLater()
    del app
