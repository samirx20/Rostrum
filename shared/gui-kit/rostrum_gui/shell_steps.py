r"""The shell's own pieces in scripted runs and the layout check (any app on the kit's AppShell): the guides drawer, the
key list, folded panels, the focused area. Called from layout_run.kit_step, which has only the bridge, so the window
is found among the app's windows (the one with AppShell's functions).

    guides open [file.md]     the guides drawer, at that guide (else the list)
    guides find <words>       the drawer's search
    keylist open              the key list (Ctrl+/)
    panels fold               Ctrl+\: the side panels fold away
    area <name>               the accent edge on that area (guides, left, centre, right, bottom)
    hover <objectName>        the pointer rests on that control (its hover help shows after 500 ms)
"""
from __future__ import annotations

from PySide6.QtCore import Q_ARG, QMetaObject, QObject
from PySide6.QtGui import QGuiApplication

WORDS = ("guides", "keylist", "panels", "area", "hover")


def window():
    """The open AppShell window (the newest, when a session opened several)."""
    wins = [w for w in QGuiApplication.topLevelWindows() if w.metaObject().indexOfMethod("openGuides()") >= 0]
    if not wins:
        raise RuntimeError("no Rostrum window (AppShell) is open")
    return wins[-1]


def do(step: str) -> bool:
    word, _, rest = step.partition(" ")
    verb, _, arg = rest.partition(" ")
    win = window()
    if word == "guides" and verb == "open":
        if arg:
            from .guides import open_named
            open_named(win, arg)
        else:
            QMetaObject.invokeMethod(win, "openGuides")
    elif word == "guides" and verb == "find":
        QMetaObject.invokeMethod(win, "openGuides")
        QMetaObject.invokeMethod(win.findChild(QObject, "guidesDrawer"), "search", Q_ARG("QVariant", arg))
    elif step == "keylist open":
        QMetaObject.invokeMethod(win, "openKeys")
    elif step == "panels fold":
        win.setProperty("panelsFolded", True)
    elif word == "area" and verb:
        win.setProperty("focusArea", verb)
    elif word == "hover" and verb:
        _hover(win, verb)
    else:
        raise ValueError(f"unknown step {step!r}: the shell's steps are {', '.join(WORDS)} (rostrum_gui/shell_steps.py)")
    return True


def _hover(win, name):
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtTest import QTest
    it = win.findChild(QObject, name)
    if it is None:
        raise ValueError(f"hover: no control named {name!r} in this window")
    p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2))
    for dx in (-3, 0):          # two moves: hover needs a move, not just a position
        QTest.mouseMove(win, QPoint(int(p.x()) + dx, int(p.y())))
