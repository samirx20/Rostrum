r"""The shell's own pieces in scripted runs and the layout check (any app on the kit's AppShell): the guides drawer, the
key list, folded panels, the focused area. Called from layout_run.kit_step, which has only the bridge, so the window
is found among the app's windows (the one with AppShell's functions).

    guides open [file.md]     the guides drawer, at that guide (else the list)
    guides find <words>       the drawer's search
    keylist open              the key list (Ctrl+/)
    panels fold               Ctrl+\: the side panels fold away
    area <name>               the accent edge on that area (guides, left, centre, right, bottom)
    hover <objectName>        the pointer rests on that control (its hover help shows after 500 ms)
    clickon <objectName>      a real mouse click on the centre of that control (an icon button with no words)
    name edit                 the project's name on the top bar, clicked: its rename field is open
    click <words>             a real mouse click (press, release) on the visible text that starts with these words,
                              e.g. "click +  New", "click Open the sample": the way a hand presses it
    mouseclick <x> <y> [right] [ctrl] [shift] [alt]   a real click at that point of the window (a clip, a note, a right-click)
    mousedrag <x0> <y0> <x1> <y1> [right] [ctrl] [shift] [alt] [altkey] [altmid] [hold]   a real drag, in small moves
    (an option word they don't know fails the step)
"""
from __future__ import annotations

from PySide6.QtCore import Q_ARG, QMetaObject, QObject
from PySide6.QtGui import QGuiApplication

from .meta import has_method

WORDS = ("guides", "keylist", "panels", "area", "hover", "name", "click", "clickon", "mouseclick", "mousedrag")


def window():
    """The open AppShell window (the newest, when a session opened several)."""
    wins = [w for w in QGuiApplication.topLevelWindows()
            if w.isVisible() and has_method(w, "openGuides()")]
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
    elif word == "clickon" and verb:
        _click_on(win, verb)
    elif word == "click" and rest:
        _click(win, rest)
    elif word == "mouseclick" and arg:
        click_at(win, rest.split())
    elif word == "mousedrag" and arg:
        drag(win, rest.split())
    elif step == "name edit":
        tab = win.findChild(QObject, "projectName")
        if tab is None or not tab.property("visible"):
            raise RuntimeError("name edit: no project name on the top bar (no project open?)")
        QMetaObject.invokeMethod(tab, "rename")
    else:
        raise ValueError(f"unknown step {step!r}: the shell's steps are {', '.join(WORDS)} (rostrum_gui/shell_steps.py)")
    return True


def _hover(win, name):
    from PySide6.QtCore import QPointF
    from .pointer import hover
    it = win.findChild(QObject, name)
    if it is None:
        raise ValueError(f"hover: no control named {name!r} in this window")
    p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2))
    hover(win, p)


def _click_on(win, name):
    from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    it = win.findChild(QObject, name)
    if it is None or not it.isVisible():
        raise ValueError(f"clickon: no visible control named {name!r} in this window")
    p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2))
    at = QPoint(int(p.x()), int(p.y()))
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    QCoreApplication.processEvents()


def _click(win, words):
    """Press and release the left button on the centre of the first visible Text starting with `words`."""
    from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt
    from PySide6.QtTest import QTest

    def visible(it):                  # the drawn tree (childItems), only through shown items
        if it.isVisible() and it.opacity() > 0:
            yield it
            for c in it.childItems():
                yield from visible(c)
    hit = next((it for it in visible(win.contentItem()) if str(it.property("text") or "").startswith(words)), None)
    if hit is None:
        raise ValueError(f"click: no visible text starting with {words!r} in this window")
    p = hit.mapToScene(QPointF(hit.width() / 2, hit.height() / 2))
    at = QPoint(int(p.x()), int(p.y()))
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    QCoreApplication.processEvents()        # the click's own handlers run (and a window it replaced goes) here


OPTIONS = {"right", "ctrl", "shift", "alt", "hold", "altkey", "altmid"}


def _opts(words, allowed):
    """The option words after the points; a word the step doesn't know fails loudly (a dropped `alt` once made an
    Alt+click check a plain click that passed)."""
    bad = [w for w in words if w not in allowed]
    if bad:
        raise ValueError(f"unknown option {' '.join(bad)!r}: the options are {', '.join(sorted(allowed))}")
    return set(words)


def _mods(opts):
    from PySide6.QtCore import Qt
    m = Qt.NoModifier
    for word, mod in (("ctrl", Qt.ControlModifier), ("shift", Qt.ShiftModifier), ("alt", Qt.AltModifier)):
        if word in opts:
            m |= mod
    return m


def drag(win, words):
    """mousedrag <x0> <y0> <x1> <y1> [right] [ctrl] [shift] [alt] [altkey] [altmid] [hold]: press, move there in ten
    steps, release (a velocity bar, a note, a fader, a layer). right: the right button; ctrl / shift / alt: held from the
    press; altkey: the Alt key pressed first, as a person does; altmid: Alt goes down halfway; hold: not let go (a
    picture mid-drag)."""
    from PySide6.QtCore import QCoreApplication, QPoint, Qt
    from PySide6.QtTest import QTest
    x0, y0, x1, y1 = (float(w) for w in words[:4])
    opts = _opts(words[4:], OPTIONS)
    button, mods = Qt.RightButton if "right" in opts else Qt.LeftButton, _mods(opts)
    if "altkey" in opts:
        QTest.keyPress(win, Qt.Key_Alt)
        mods |= Qt.AltModifier
    QTest.mouseMove(win, QPoint(int(x0), int(y0)))
    QTest.mousePress(win, button, mods, QPoint(int(x0), int(y0)))
    for i in range(1, 11):
        if i == 5 and "altmid" in opts:
            QTest.keyPress(win, Qt.Key_Alt)
            mods |= Qt.AltModifier
        QTest.mouseMove(win, QPoint(int(x0 + (x1 - x0) * i / 10), int(y0 + (y1 - y0) * i / 10)))
        QCoreApplication.processEvents()
    if "hold" in opts:
        return
    QTest.mouseRelease(win, button, mods, QPoint(int(x1), int(y1)))
    if opts & {"altkey", "altmid"}:
        QTest.keyRelease(win, Qt.Key_Alt)
    QCoreApplication.processEvents()


def click_at(win, words):
    """mouseclick <x> <y> [right] [ctrl] [shift] [alt]: press and release there, as a hand does (moved there first)."""
    from PySide6.QtCore import QCoreApplication, QPoint, Qt
    from PySide6.QtTest import QTest
    at, opts = QPoint(int(float(words[0])), int(float(words[1]))), _opts(words[2:], {"right", "ctrl", "shift", "alt"})
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.RightButton if "right" in opts else Qt.LeftButton, _mods(opts), at)
    QCoreApplication.processEvents()
