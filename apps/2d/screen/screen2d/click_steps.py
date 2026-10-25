"""Scripted steps that click any control the way a hand would (QTest, the real mouse path), found by its objectName:
    clickobj <objectName> [fx fy] [right]   the control's point at fractions fx, fy of its box (default its centre);
                                       `right`: a right-click; prints how long the click's work took
    hoverobj <objectName> [ms]         the pointer rests on the control (default 700 ms: past the hover-preview delay, then the preview is drawn)
    typekeys <text>                    type it on the keyboard into what has focus (_ for a space)
    dragobj <objectName> fx0 fy0 fx1 fy1   press at one point of the control's box, move, release at the other
    picturefile <path>                 the open paint picker's picture dialog picks this file (after clickobj fillType:picture)
    choicefile <row id> <path>         a choice's "Load …" dialog (Tip picture's Load picture…) picks this file
Used for the colour picker's proofs (the Fill row "row:paint", the picker's own named parts)."""
from __future__ import annotations
from rostrum_gui.pointer import wait  # never QTest.qWait: it starves the worker threads

WORDS = {"clickobj", "dragobj", "hoverobj", "picturefile", "choicefile", "typekeys"}


def do_click_step(win, word, rest, step):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    wait(400)                         # the panel's reveals (160 ms) settle first: a hand clicks what it sees
    if word == "picturefile":                # a file dialog can't be clicked by script: hand it the file it would give
        from pathlib import Path
        from PySide6.QtCore import Q_ARG, QMetaObject, QUrl
        pic = _named(win, "picturePaint", shown=False)
        if pic is None:
            raise RuntimeError(f"step {step!r}: the paint picker isn't open")
        QMetaObject.invokeMethod(pic, "accept", Q_ARG("QVariant", QUrl.fromLocalFile(str(Path(rest[0]).resolve())).toString()))
        wait(150)
        return
    if word == "typekeys":
        QTest.keyClicks(win, " ".join(rest).replace("_", " "))
        wait(100)
        return
    if word == "choicefile":
        from pathlib import Path
        from PySide6.QtCore import Q_ARG, QMetaObject
        row = _named(win, f"row:{rest[0]}")
        if row is None:
            raise RuntimeError(f"step {step!r}: no settings row {rest[0]!r} on screen")
        QMetaObject.invokeMethod(row, "loadChoice", Q_ARG("QVariant", str(Path(rest[1]).resolve())))
        wait(300)
        return
    item = _named(win, rest[0])
    if item is None:
        raise RuntimeError(f"step {step!r}: no visible control named {rest[0]!r}")

    def at(fx, fy):
        q = item.mapToScene(QPointF(float(fx) * item.property("width"), float(fy) * item.property("height")))
        return QPoint(round(q.x()), round(q.y()))
    if word == "hoverobj":
        from rostrum_gui.pointer import hover
        hover(win, at(0.5, 0.5), int(rest[1]) if rest[1:] else 700)
        return
    if word == "clickobj":
        right = rest[-1] == "right"
        win.grabWindow()                      # a window kept behind the person's work may not have drawn (laid out) since
        p = at(*([w for w in rest[1:3] if w != "right"] or (0.5, 0.5)))      # the last change: a hand sees it drawn
        QTest.mouseMove(win, p)
        import time
        from PySide6.QtCore import QCoreApplication
        t0 = time.perf_counter()
        QTest.mouseClick(win, Qt.RightButton if right else Qt.LeftButton, Qt.NoModifier, p)
        QCoreApplication.processEvents()          # what the click set off (the change, the rows) is handled
        print(f"clickobj {rest[0]}: {(time.perf_counter() - t0) * 1000:.1f} ms", flush=True)
    else:
        a, b = at(*rest[1:3]), at(*rest[3:5])
        QTest.mouseMove(win, a)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
        for i in range(1, 9):
            QTest.mouseMove(win, a + (b - a) * i / 8, 10)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, b)
    wait(150)


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
