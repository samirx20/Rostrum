"""The canvas pointers (CURSORS.md): a turned pointer keeps its hotspot exact, angles snap to 5° steps, each pointer is
made once, an unknown name fails loudly, and a held key changes the pointer with the mouse still (CANVAS 1.1).

The held-key check runs a real window behind the person's work on Windows' own screen platform, in its own process:
an offscreen window has no real pointer to set."""
import os
import subprocess
import sys

import pytest

WINDOW = """
import QtQuick
import RostrumCursors
Window {
    width: 400; height: 300
    Rectangle { x: 50; y: 50; width: 200; height: 150; color: "#333"
        CanvasCursor { objectName: "cc"; kind: "pick"; altBadge: "copy"; ctrlBadge: "deep" } }
}
"""


@pytest.fixture(scope="module")
def qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    return QGuiApplication.instance() or QGuiApplication(sys.argv)


def test_a_turned_pointer_keeps_its_hotspot(qt):
    from rostrum_gui.cursors import picture
    for angle in range(0, 360, 5):         # the two-headed arrow is the same turned half way round its hotspot
        img, hot = picture("resize", angle)
        for dx in range(-9, 10):
            for dy in range(-9, 10):
                a = img.pixelColor(hot.x() + dx, hot.y() + dy).alpha() if img.valid(hot.x() + dx, hot.y() + dy) else 0
                b = img.pixelColor(hot.x() - dx, hot.y() - dy).alpha() if img.valid(hot.x() - dx, hot.y() - dy) else 0
                assert abs(a - b) <= 40, f"resize@{angle}: not centred on its hotspot at {dx},{dy} ({a} vs {b})"
    for scale in (1.0, 1.5, 2.0):          # the pick arrow's tip is the hotspot pixel at every size and turn
        for angle in (0, 20, 135):
            img, hot = picture("pick", angle, "", scale)
            assert img.pixelColor(hot).alpha() > 60, f"pick@{angle} x{scale}: hotspot off the tip"


def test_angles_snap_and_each_pointer_is_made_once(qt):
    from rostrum_gui.cursors import cursor, snap
    assert [snap(a) * 5 for a in (0, 2.4, 2.6, 92, 359, -5)] == [0, 0, 5, 90, 0, 355]
    assert cursor("rotate", 31, "", 1.5) is cursor("rotate", 29, "", 1.5)
    assert cursor("pick", 0, "copy") is not cursor("pick", 0, "deep")


def test_an_unknown_name_fails_loudly(qt):
    from rostrum_gui.cursor_item import CanvasCursor
    from rostrum_gui.cursors import cursor
    with pytest.raises(ValueError, match="kind"):
        cursor("arow")
    with pytest.raises(ValueError, match="badge"):
        cursor("pick", 0, "cpoy")
    item = CanvasCursor()
    with pytest.raises(ValueError):
        item.kind = "arow"
    assert item.kind == "pick"


def test_theme_names_match():
    """Theme.qml's cursorKinds / cursorBadges, once added, list exactly cursors.py's names."""
    import re
    from rostrum_gui.cursors import BADGES, KINDS, THEME
    text = THEME.read_text(encoding="utf-8")
    for prop, names in (("cursorKinds", KINDS), ("cursorBadges", BADGES)):
        m = re.search(rf"property var {prop}:\s*\[([^\]]*)\]", text)
        if m:
            assert re.findall(r'"([^"]+)"', m.group(1)) == list(names), f"Theme.{prop} differs from cursors.py"


def run(folder):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
    import checkout_paths
    checkout_paths.use_this_checkout()
    from PySide6.QtCore import QObject, QPoint, Qt
    from PySide6.QtTest import QTest
    from rostrum_gui.app import start, stop
    from rostrum_gui.cursors import cursor, scale_for
    from rostrum_gui.pointer import hover, wait
    main = os.path.join(folder, "Main.qml")
    open(main, "w", encoding="utf-8").write(WINDOW)
    app, engine, win = start(main, {}, (400, 300))
    try:
        cc = win.findChild(QObject, "cc")
        hover(win, QPoint(120, 120))

        def showing(badge):
            want = cursor("pick", 0, badge, scale_for(win), win.devicePixelRatio())
            got = win.cursor()
            return got.shape() == Qt.CursorShape.BitmapCursor and got.hotSpot() == want.hotSpot() and \
                got.pixmap().toImage() == want.pixmap().toImage()
        assert showing(""), "the hovered pointer is not the plain pick arrow"
        for key, badge in ((Qt.Key.Key_Alt, "copy"), (Qt.Key.Key_Control, "deep")):
            QTest.keyPress(win, key)              # no mouse move from here on
            wait(1)
            assert cc.property("shown") == f"pick+{badge}@0", cc.property("shown")
            assert showing(badge), f"{badge}: the window's pointer did not change on the key alone"
            QTest.keyRelease(win, key)
            wait(1)
            assert showing(""), f"{badge}: the pointer did not go back on release"
    finally:
        stop(engine, win)


def test_a_held_key_changes_the_pointer_with_the_mouse_still(tmp_path):
    env = {**os.environ, "ROSTRUM_BACKGROUND_WINDOWS": "1"}
    if os.name == "nt":
        env["QT_QPA_PLATFORM"] = "windows"
    done = subprocess.run([sys.executable, os.path.abspath(__file__), str(tmp_path)], env=env, capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-1500:]


if __name__ == "__main__":
    run(sys.argv[1])
