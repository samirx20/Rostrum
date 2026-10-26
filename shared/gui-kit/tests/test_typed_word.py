"""A word typed with no box focused runs no commands (Sound critic r9 + r10: typing "drums" added a marker from its M
and put the S into the marker's name), but two quick commands both run (critic r11: B then V lost the V, Space-Space
lost the stop), and a text field gets every letter however fast."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QKeyEvent  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402,F401  (the root object comes back as a QQuickWindow)
from PySide6.QtTest import QTest  # noqa: E402

from rostrum_gui import typed_word  # noqa: E402

# the kit's KeyShortcut reports each firing to `typedWord`; these stand-ins do the same
WINDOW = b"""
import QtQuick
import QtQuick.Window
Window { width: 300; height: 200; visible: true
    property int marks: 0
    property int draws: 0
    property int selects: 0
    property int plays: 0
    property alias text: field.text
    component Key: Shortcut { context: Qt.ApplicationShortcut; onActivated: typedWord.ran() }
    Key { sequence: "M"; onActivated: marks++ }
    Key { sequence: "B"; onActivated: draws++ }
    Key { sequence: "V"; onActivated: selects++ }
    Key { sequence: "Space"; onActivated: plays++ }
    TextInput { id: field; objectName: "field"; width: 200; height: 30; selectByMouse: true }
}
"""


def _window():
    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    now = [100.0]
    words = typed_word.make(clock=lambda: now[0])
    engine.rootContext().setContextProperty("typedWord", words)
    engine.loadData(WINDOW)
    win = engine.rootObjects()[0]
    words.watch(win)
    QTest.qWait(50)
    win.contentItem().forceActiveFocus()

    def key(k, after):
        now[0] += after
        QTest.keyClick(win, k)
    key.now = now
    return app, engine, win, words, key


def test_a_word_runs_no_command_but_a_lone_key_and_a_field_do():
    app, engine, win, words, key = _window()
    key(Qt.Key_M, 1.0)
    assert win.property("marks") == 1, "a lone M (a command key) did nothing"
    for k in (Qt.Key_D, Qt.Key_R, Qt.Key_U, Qt.Key_M, Qt.Key_S):     # "drums", typed: D is no command
        key(k, 0.08 if k != Qt.Key_D else 1.0)
    assert win.property("marks") == 1, "the M inside a typed word ran its command"
    key(Qt.Key_M, 1.0)
    assert win.property("marks") == 2, "a lone M after the word did nothing"

    for k, ch, after in ((Qt.Key_D, "d", 1.0), (Qt.Key_M, "m", 0.05)):   # presses sent straight to the window (a script's)
        key.now[0] += after
        QCoreApplication.sendEvent(win, QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier, ch))
    assert win.property("marks") == 2, "an M sent straight to the window inside a word ran its command"
    engine.deleteLater()


def test_quick_commands_all_run():
    app, engine, win, words, key = _window()
    key(Qt.Key_B, 1.0)
    key(Qt.Key_V, 0.2)                                              # Draw then Select, 200 ms apart
    assert (win.property("draws"), win.property("selects")) == (1, 1), "V right after B was dropped"
    key(Qt.Key_Space, 1.0)
    key(Qt.Key_Space, 0.2)                                          # play, then stop
    assert win.property("plays") == 2, "the second Space was dropped"
    key(Qt.Key_M, 1.0)
    key(Qt.Key_Space, 0.28)                                         # a marker, then play
    assert (win.property("marks"), win.property("plays")) == (1, 3), "Space after M was dropped"
    engine.deleteLater()


def test_a_field_gets_every_key_however_fast():
    app, engine, win, words, key = _window()
    win.findChild(object, "field").forceActiveFocus()
    for k in (Qt.Key_M, Qt.Key_1, Qt.Key_2, Qt.Key_Period, Qt.Key_5, Qt.Key_X):
        key(k, 0.015)
    assert win.property("text") == "m12.5x" and win.property("marks") == 0, "a text field lost keys to the guard"
    engine.deleteLater()
