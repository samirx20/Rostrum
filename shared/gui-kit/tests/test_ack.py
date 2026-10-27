"""Every press answers in the frame of the press, a slow action shows life, a second click is never lost (ack.py), and a
letter in a number box says one line (INTERACTION.md principles 1, 2, 8). Real QTest clicks and keys on a window."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace  # noqa: E402

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402,F401
from PySide6.QtTest import QTest  # noqa: E402

from rostrum_gui import ack, typed_word  # noqa: E402
from rostrum_gui.action_hub import ActionHub  # noqa: E402
from rostrum_gui.actions import Action, ActionList  # noqa: E402
from rostrum_gui.app import KIT_QML  # noqa: E402
from rostrum_gui.keymap import KeyMap  # noqa: E402

WINDOW = b"""
import QtQuick
import QtQuick.Window
import RostrumKit
Window { width: 400; height: 200; visible: true; color: "#141414"
    Button { objectName: "slow"; x: 20; y: 40; width: 100; text: "Slow"; onClicked: hub.run("slow") }
    Button { objectName: "quick"; x: 140; y: 40; width: 100; text: "Quick"; onClicked: hub.run("quick") }
    NumberField { objectName: "num"; x: 20; y: 100; width: 120; height: 24; value: 5 }
    Loader { x: 0; y: 0; width: 400; source: kitDir + "/WorkingLine.qml"   // (inside the kit: TopBar's)
             onLoaded: { item.objectName = "line"; item.width = 400 } }
}
"""


def _slow(fn):
    out = fn()
    if out is not None:                 # a generator: the action's long part goes on in turns
        ack.ACK.in_turns(out)


def _window(slow_fn, heavy=False):
    app = QGuiApplication.instance() or QGuiApplication([])
    ran = []
    acts = [Action("slow", "Group", do="slow", min_targets=0, heavy=heavy), Action("quick", "Quick", do="quick", min_targets=0)]
    hub = ActionHub(ActionList(acts, KeyMap("test")), lambda: SimpleNamespace(ids=["a"] * 5, items=[]),
                    lambda f: "5 layers", None, lambda d, e: (ran.append(d), _slow(slow_fn) if d == "slow" else None),
                    lambda line: None)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(KIT_QML))
    ctx = engine.rootContext()
    words = typed_word.make()
    for k, v in {"uiFont": "Segoe UI", "monoFont": "Consolas", "ack": ack.ACK, "hub": hub, "typedWord": words,
                 "kitDir": (KIT_QML / "RostrumKit").as_uri()}.items():
        ctx.setContextProperty(k, v)
    engine.loadData(WINDOW)
    win = engine.rootObjects()[0]
    words.watch(win)
    QTest.qWait(30)
    return app, engine, win, hub, ran


def _centre(win, name):
    it = win.findChild(QQuickItem, name)
    p = it.mapToScene(it.boundingRect().center())
    return it, QPoint(int(p.x()), int(p.y()))


def test_press_shows_in_its_own_frame_and_a_slow_action_shows_life_and_keeps_the_next_click():
    def slow():                         # a job in turns: the window draws between them
        end = time.monotonic() + 0.5
        while time.monotonic() < end:
            time.sleep(0.01)
            yield
    app, engine, win, hub, ran = _window(slow, heavy=True)     # it says it is long: its press is drawn first
    button, at = _centre(win, "slow")
    QTest.mouseMove(win, at)
    QTest.qWait(200)                    # the hover has faded in
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, at)
    assert win.grabWindow().pixelColor(at.x(), at.y() - 8).name() == "#333333", "the press was not drawn in its frame"
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, at)
    line = win.findChild(QQuickItem, "line")
    assert ran == [] and button.property("working") and line.isVisible(), "the action ran before its press was drawn"
    assert ack.ACK.property("note") == "Group · 5 layers…"
    _, quick = _centre(win, "quick")
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, quick)      # a second click while the first waits
    assert win.grabWindow().pixelColor(at.x(), at.y() - 8).name() == "#333333", "the working button lost its pressed look"
    words = line.findChild(QQuickItem, "workingWords")
    spot = words.mapToScene(words.boundingRect().topLeft())
    seen = {}
    t0 = time.monotonic()
    while time.monotonic() - t0 < 0.35:  # the slow action runs in turns; the window draws as a shown one does
        img = win.grabWindow()
        seen.setdefault(img.pixelColor(int(spot.x()) + 3, int(spot.y()) + 3).name() != "#141414", round(time.monotonic() - t0, 3))
        QTest.qWait(15)
    assert ran == ["slow"], "the slow action did not start, or the second click jumped the line"
    assert seen.get(True, 9) <= 0.2, f"no sign of life by 0.2 s into an action known to be long ({seen})"
    end = time.monotonic() + 3
    while ack.ACK.busy() and time.monotonic() < end:
        QTest.qWait(20)
    assert ran == ["slow", "quick"], "the click made during the wait was lost"
    assert not button.property("working") and not line.isVisible()
    engine.deleteLater()


def test_a_plain_action_known_to_be_slow_shows_its_line_before_it_starts():
    app, engine, win, hub, ran = _window(lambda: time.sleep(0.25))
    _, at = _centre(win, "slow")
    ack.ACK.forget_times()
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    assert ran == ["slow"]              # not known long yet: it ran at once, inside its click, and was measured: 0.25 s
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    line = win.findChild(QQuickItem, "line")
    win.grabWindow()                    # the frame before the run: the line is already coming in
    assert ran == ["slow"] and line.isVisible() and ack.ACK.property("lineAfter") == 0
    ack.ACK.flush()
    assert ran == ["slow", "slow"]
    engine.deleteLater()


def test_a_letter_in_a_number_box_says_so():
    app, engine, win, hub, ran = _window(lambda: None)
    num, at = _centre(win, "num")
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    QTest.qWait(30)
    tip = next(c for c in num.findChildren(QQuickItem) if c.property("text") == "Type a number, like 12 or +5")
    QTest.keyClick(win, Qt.Key_1)
    QTest.qWait(30)
    assert not tip.property("shown")
    QTest.keyClick(win, Qt.Key_Q)
    QTest.qWait(30)
    assert tip.property("shown"), "a letter in a number box vanished without a word"
    assert win.activeFocusItem().property("text") == "1", "the letter stayed in the number, or the typing was lost"
    engine.deleteLater()
