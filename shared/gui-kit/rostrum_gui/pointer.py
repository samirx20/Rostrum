"""The one place a script rests the pointer on a control (a real hover, as a hand does it): hover-only controls (the
eye and lock on a layer row, a marker flag's x, a Library row's tip) show only for a pointer that arrived by moving.

    hover(win, point, ms=0)     arrive at `point` (window px) in two small moves, then wait `ms` (a tip shows after 500)
    wait(ms)                    let the window run for `ms`, as its own event loop does. Never QTest.qWait: it keeps
                                Python's lock and starves every worker thread ~100x (an 0.4 s Lottie export took 100 s)

Plain QTest moves are real hover events; what once hid every hover from scripts was a tip's own layer in the kit
(HoverTip.qml) taking the hover away from the control under it, not the move. The two moves still matter: a pointer
that is only placed (one move onto a new spot after a click on it) may not have entered the control."""
from __future__ import annotations


def hover(win, point, ms: int = 0) -> None:
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    p = QPoint(int(point.x()), int(point.y()))
    QTest.mouseMove(win, p + QPoint(-3, 0))
    QTest.mouseMove(win, p)
    wait(max(ms, 30))


def wait(ms: int) -> None:
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(int(ms), loop.quit)
    loop.exec()


def wait_until(condition, what: str, timeout_ms: int = 5000) -> None:
    """Run the window in short slices until `condition()` is true; fail loudly (naming `what`) at the deadline."""
    import time
    end = time.monotonic() + timeout_ms / 1000
    while not condition():
        if time.monotonic() > end:
            raise AssertionError(f"timed out after {timeout_ms} ms waiting for: {what}")
        wait(15)
