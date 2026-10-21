"""Drive the real window with synthetic keys and clicks and print what changed:  python check_input.py

Steps run on timers, never QTest.qWait (README › Threading). Expected: playing flips False then True, selectedIndex
2 then 4, viewMode=video after Ctrl+K "show vid" Enter, playhead jumps on the timeline click and is near 0 after Home.
"""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.argv = ["main.py", "--mode", "viewport", "--screenshot", "unused.png"]  # --screenshot arms the 15 s watchdog
sys.path.insert(0, str(HERE))
from PySide6.QtCore import QPoint, QTimer, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

import measure  # noqa: E402


def win():
    return QGuiApplication.topLevelWindows()[0]


def show(*names):
    print(" ".join(f"{n}={win().property(n)}" for n in names), flush=True)


def type_text(w, text):
    for c in text:
        QTest.keyClick(w, Qt.Key_Space if c == " " else getattr(Qt, "Key_" + c.upper()))


def steps():
    w = win()
    yield lambda: show("viewMode", "playing", "selectedIndex")
    yield lambda: QTest.keyClick(w, Qt.Key_Space)
    yield lambda: show("playing")
    yield lambda: QTest.keyClick(w, Qt.Key_Space)
    yield lambda: show("playing")
    yield lambda: (QTest.keyClick(w, Qt.Key_Down), QTest.keyClick(w, Qt.Key_Down))
    yield lambda: show("selectedIndex")
    yield lambda: QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(100, 40 + 32 + 8 + 4 * 30 + 14))  # 5th row
    yield lambda: show("selectedIndex")
    yield lambda: QTest.keyClick(w, Qt.Key_K, Qt.ControlModifier)
    yield lambda: type_text(w, "show vid")
    yield lambda: QTest.keyClick(w, Qt.Key_Return)
    yield lambda: show("viewMode")
    yield lambda: QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(256 + 12 + 600, w.height() - 8 - 12 - 50))
    yield lambda: show("playhead")
    yield lambda: QTest.keyClick(w, Qt.Key_Home)
    yield lambda: show("playhead")


_it = None


def tick():
    global _it
    _it = _it or steps()
    try:
        next(_it)()
        QTimer.singleShot(300, tick)
    except StopIteration:
        QGuiApplication.exit(0)


measure.screenshot_later = lambda *a, **k: QTimer.singleShot(2500, tick)
runpy.run_path(str(HERE / "main.py"), run_name="__main__")
