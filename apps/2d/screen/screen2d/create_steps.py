"""Scripted steps for the creation tools (steps.py hands these over); each goes through the calls the mouse and keys make.

    shape <rect|ellipse> x0 y0 x1 y1 [shift] [alt]   press at (x0, y0), drag to (x1, y1), let go (composition px)
    shapedrag <rect|ellipse> x0 y0 x1 y1 [shift] [alt]   the same, held before letting go (for a picture of the live outline)
    shapeend x1 y1 [shift] [alt]                     let go of a shapedrag
    text <x> <y> <words…>                            T, click at (x, y), type, Esc (_ for spaces, | for a new line)
    textbox <x0> <y0> <x1> <y1> <words…>             T, drag a box, type, Esc
    typetext <x> <y> <words…>                        the same, but typing is not ended (for a picture of the cursor)
    edittext <layer> <words…>                        double-click the text, replace all of it, Esc
    endtext                                          Esc
  A hand's real mouse and keys in the window (QTest), at composition px (the Stage's mapping):
    canvasdrag <x0> <y0> <x1> <y1>                   press, pull, let go
    canvasclick <x> <y> [double]                     one click (or two quick ones)
    typekeys <words…>                                real key presses into what has the focus (_ for spaces)
"""
from __future__ import annotations

WORDS = ("shape", "shapedrag", "shapeend", "text", "textbox", "typetext", "edittext", "endtext", "canvasdrag", "canvasclick",
         "typekeys")
SLOP = 4.0


def _words(rest) -> str:
    return " ".join(rest).replace("|", "\n")


def _typed(c, body):
    for i in range(1, len(body) + 1):                       # key by key, as typing is
        c.typeText(body[:i])


def _hand(word, rest):
    from PySide6.QtCore import QObject, QPoint, QPointF, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    win = next(w for w in QGuiApplication.topLevelWindows() if w.findChild(QObject, "stage"))
    stage = win.findChild(QObject, "stage")
    o, k = stage.property("compOrigin"), stage.property("compScale")

    def at(x, y):
        q = stage.mapToScene(QPointF(o.x() + float(x) * k, o.y() + float(y) * k))
        return QPoint(round(q.x()), round(q.y()))
    if word == "typekeys":
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        for ch in " ".join(rest).replace("_", " "):         # as a keyboard sends them: a press and a release with the letter
            key, mod = Qt.Key(ord(ch.upper())), Qt.ShiftModifier if ch.isupper() else Qt.NoModifier
            for kind in (QEvent.KeyPress, QEvent.KeyRelease):
                QGuiApplication.sendEvent(win, QKeyEvent(kind, key, mod, ch))
            QTest.qWait(10)
    elif word == "canvasclick":
        p = at(*rest[:2])
        QTest.mouseMove(win, p)
        if rest[2:3] == ["double"]:
            QTest.mouseDClick(win, Qt.LeftButton, Qt.NoModifier, p)
        else:
            QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, p)
    else:
        a, b = at(*rest[:2]), at(*rest[2:4])
        QTest.mouseMove(win, a)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
        for i in range(1, 9):
            QTest.mouseMove(win, a + (b - a) * i / 8, 10)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, b)
    QTest.qWait(120)


def do_create_step(bridge, word, rest, step):
    if word in ("canvasdrag", "canvasclick", "typekeys"):
        return _hand(word, rest)
    c = bridge.create
    flags = [w for w in rest if w in ("shift", "alt")]
    rest = [w for w in rest if w not in ("shift", "alt")]
    shift, alt = "shift" in flags, "alt" in flags
    if word in ("shape", "shapedrag"):
        kind, x0, y0, x1, y1 = rest[0], *map(float, rest[1:5])
        bridge.setTool(kind)
        c.beginShape(kind, x0, y0, SLOP)
        c.dragShape(x1, y1, shift, alt)
        if word == "shape":
            c.endShape(x1, y1, shift, alt)
    elif word == "shapeend":
        c.endShape(float(rest[0]), float(rest[1]), shift, alt)
    elif word in ("text", "typetext"):
        bridge.setTool("text")
        c.beginText(float(rest[0]), float(rest[1]), 0)
        _typed(c, _words(rest[2:]).replace("_", " "))
        if word == "text":
            c.commitText(c.body)
    elif word == "textbox":
        x0, y0, x1, y1 = map(float, rest[:4])
        bridge.setTool("text")
        c.beginText(min(x0, x1), min(y0, y1), abs(x1 - x0))
        _typed(c, _words(rest[4:]).replace("_", " "))
        c.commitText(c.body)
    elif word == "edittext":
        c.editText(rest[0])
        _typed(c, _words(rest[1:]).replace("_", " "))
        c.commitText(c.body)
    elif word == "endtext":
        c.commitText(c.body)
