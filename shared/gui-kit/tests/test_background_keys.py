"""A window opened behind the person's work (background mode) is never the active window, yet a real key press on it
reaches the window's shortcuts: the kit's Ctrl+K and an app's own Shortcut. It must not take the keyboard or come to
the front (the bug: every scripted key check of a background window silently did nothing).

The test runs the window in its own process on Windows' real screen platform: an offscreen window is always active,
which hides the bug, and the test process shares one offscreen app."""
import os
import subprocess
import sys

WINDOW = """
import QtQuick
import RostrumKit
AppShell {
    bridge: theBridge; helpEntries: []
    property int hits: 0
    centre: Item { anchors.fill: parent
        Shortcut { sequence: "Ctrl+J"; onActivated: hits++ } }
}
"""


def run(folder):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
    import checkout_paths
    checkout_paths.use_this_checkout()
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    from rostrum_core import toy
    from rostrum_gui import DocBridge
    from rostrum_gui.app import start, stop
    main = os.path.join(folder, "Main.qml")
    open(main, "w", encoding="utf-8").write(WINDOW)
    bridge = DocBridge(toy.sample())
    app, engine, win = start(main, {"theBridge": bridge}, (1200, 800))
    try:
        QTest.qWait(300)
        QTest.keyClick(win, Qt.Key_J, Qt.ControlModifier)
        assert win.property("hits") == 1, "an app's own shortcut did nothing in a background window"
        QTest.keyClick(win, Qt.Key_K, Qt.ControlModifier)
        QTest.qWait(400)
        bar = [o for o in win.findChildren(QObject) if o.metaObject().className().startswith("CommandBar")]
        assert bar and bar[0].property("opened"), "Ctrl+K did not open the command box in a background window"
        assert not win.isActive() and QGuiApplication.focusWindow() is None, "the check took the keyboard"
    finally:
        stop(engine, win, then=bridge.deleteLater)


def test_keys_reach_a_background_window_without_activating_it(tmp_path):
    env = {**os.environ, "ROSTRUM_BACKGROUND_WINDOWS": "1"}
    if os.name == "nt":
        env["QT_QPA_PLATFORM"] = "windows"
    done = subprocess.run([sys.executable, os.path.abspath(__file__), str(tmp_path)], env=env, capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-1500:]


if __name__ == "__main__":
    run(sys.argv[1])
