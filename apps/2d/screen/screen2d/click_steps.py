"""Scripted steps that click any control the way a hand would (QTest, the real mouse path), found by its objectName:
    clickobj <objectName> [fx fy]      the control's point at fractions fx, fy of its box (default its centre)
    dragobj <objectName> fx0 fy0 fx1 fy1   press at one point of the control's box, move, release at the other
    picturefile <path>                 the open paint picker's picture dialog picks this file (after clickobj fillType:picture)
Used for the colour picker's proofs (the Fill row "row:paint", the picker's own named parts)."""
from __future__ import annotations

WORDS = {"clickobj", "dragobj", "picturefile"}


def do_click_step(win, word, rest, step):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    QTest.qWait(400)                         # the panel's reveals (160 ms) settle first: a hand clicks what it sees
    if word == "picturefile":                # a file dialog can't be clicked by script: hand it the file it would give
        from pathlib import Path
        from PySide6.QtCore import Q_ARG, QMetaObject, QUrl
        pic = _named(win, "picturePaint", shown=False)
        if pic is None:
            raise RuntimeError(f"step {step!r}: the paint picker isn't open")
        QMetaObject.invokeMethod(pic, "accept", Q_ARG("QVariant", QUrl.fromLocalFile(str(Path(rest[0]).resolve())).toString()))
        QTest.qWait(150)
        return
    item = _named(win, rest[0])
    if item is None:
        raise RuntimeError(f"step {step!r}: no visible control named {rest[0]!r}")

    def at(fx, fy):
        q = item.mapToScene(QPointF(float(fx) * item.property("width"), float(fy) * item.property("height")))
        return QPoint(round(q.x()), round(q.y()))
    if word == "clickobj":
        p = at(*(rest[1:3] or (0.5, 0.5)))
        QTest.mouseMove(win, p)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, p)
    else:
        a, b = at(*rest[1:3]), at(*rest[3:5])
        QTest.mouseMove(win, a)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
        for i in range(1, 9):
            QTest.mouseMove(win, a + (b - a) * i / 8, 10)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, b)
    QTest.qWait(150)


def _named(win, name, shown=True):
    """The visible item called `name`, anywhere in the window's item tree (popups in the overlay included)."""
    top = win.contentItem()
    todo = [top.parentItem() or top]
    while todo:
        o = todo.pop()
        if o.objectName() == name and (o.isVisible() or not shown):
            return o
        todo.extend(o.childItems())
    return None
