"""The one place a script rests the pointer on a control (a real hover, as a hand does it): hover-only controls (the
eye and lock on a layer row, a marker flag's x, a Library row's tip) show only for a pointer that arrived by moving.

    hover(win, point, ms=0)     arrive at `point` (window px) in two small moves, then wait `ms` (a tip shows after 500)

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
    QTest.qWait(max(ms, 30))
