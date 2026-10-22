"""Scripted steps for picking colours, selecting strokes and the focused area (paint_steps.py hands these over); each goes
through the calls the pointer and keys make.

    altpick <x> <y> [click]        hold Alt with the pointer at (x, y) (composition px): the swatch shows the colour there;
                                   `click` picks it as the brush colour. `altoff` lets go of Alt
    lasso <x,y> <x,y> … [open]     Ctrl+drag a lasso (composition px); `open` leaves it undrawn-to-the-end (a picture of it)
    selectstrokes on|off           the bar's Select strokes (the next drag is a lasso)
    strokesmove <dx> <dy>          drag the picked strokes by that much | strokesturn <deg> [scale] | strokesdelete |
    strokescopy | strokespaste | strokesclear (Esc)
    clickarea canvas|timeline|settings    a real click in that part of the window (the focused area follows it)
    windowsize <W>x<H>             resize the window now (a picture of an open menu needs the final size before it opens)
    barbutton <label>              open that context-bar button's ▾ menu (Set depth)
    clickat <x> <y>                a real click at that window point (logical px)
"""
from __future__ import annotations

from PySide6.QtCore import Q_ARG, QObject, QCoreApplication, QMetaObject, QPoint, QPointF, Qt
from PySide6.QtTest import QTest

WORDS = ("altpick", "altoff", "lasso", "selectstrokes", "strokesmove", "strokesturn", "strokesdelete", "strokescopy",
         "strokespaste", "strokesclear", "clickarea", "clickat", "barbutton", "windowsize")

# where an empty spot of each area is, as fractions of the window (width, height)
AREAS = {"canvas": (0.45, 0.30), "timeline": (0.60, 0.93), "settings": (0.93, 0.55)}


def _walk(item):
    todo = [item]
    while todo:
        o = todo.pop()
        yield o
        todo.extend(o.childItems())


def do_stroke_step(bridge, win, word, rest, step):
    pick, sel = bridge.colourPick, bridge.strokeSelect
    if word == "altpick":
        pick.setAlt(True)
        x, y = float(rest[0]), float(rest[1])
        pick.look(x, y)
        if rest[1:2] and "click" in rest[2:] and not pick.pickAt(x, y):
            raise RuntimeError(f"step {step!r}: {bridge.status}")
    elif word == "altoff":
        pick.setAlt(False)
    elif word == "lasso":
        points = [[float(v) for v in p.split(",")] for p in rest if p != "open"]
        sel.beginLasso(*points[0])
        for p in points[1:]:
            sel.lassoTo(*p)
        if "open" not in rest and sel.endLasso() == 0:
            raise RuntimeError(f"step {step!r}: no strokes inside the lasso")
    elif word == "selectstrokes":
        sel.arm(rest[0] == "on")
    elif word == "strokesmove":
        if not sel.move(float(rest[0]), float(rest[1])):
            raise RuntimeError(f"step {step!r}: no strokes picked")
    elif word == "strokesturn":
        if not sel.transform(float(rest[1]) if rest[1:] else 1.0, float(rest[0])):
            raise RuntimeError(f"step {step!r}: no strokes picked")
    elif word == "strokesdelete":
        if not sel.remove():
            raise RuntimeError(f"step {step!r}: no strokes picked")
    elif word == "strokescopy":
        sel.copy()
    elif word == "strokespaste":
        if not sel.paste():
            raise RuntimeError(f"step {step!r}: nothing to paste")
    elif word == "strokesclear":
        sel.clear()
    elif word == "windowsize":
        w, h = (int(v) for v in rest[0].split("x"))
        win.resize(w, h)
        for _ in range(8):
            QCoreApplication.processEvents()
            QTest.qWait(60)
    elif word == "barbutton":
        label, todo = " ".join(rest), [win.contentItem()]
        while todo:
            o = todo.pop()
            m = o.property("modelData")
            m = m.toVariant() if hasattr(m, "toVariant") else m
            if isinstance(m, dict) and m.get("label") == label and o.property("hasMenu") is not None:
                c = o.mapToScene(QPointF(0, o.height() + 2))
                menu = next((i for up in (o, o.parentItem()) for i in up.findChildren(QObject) if i.property("entries")), None)       # its ActionMenu (ContextBar.qml `choices`)
                if menu is None:
                    raise RuntimeError(f"step {step!r}: {label!r} has no menu")
                QMetaObject.invokeMethod(menu, "openAt", Q_ARG("QVariant", c.x()), Q_ARG("QVariant", c.y()), Q_ARG("QVariant", c.x() + o.width()))
                QTest.qWait(400)                    # the menu opens with a short reveal
                break
            todo.extend(o.childItems())
        else:
            raise RuntimeError(f"step {step!r}: no context-bar button called {label!r}")
    elif word == "clickat":
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(rest[0]), int(rest[1])))
        QCoreApplication.processEvents()
    elif word == "clickarea":
        fx, fy = AREAS[rest[0]]
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(win.width() * fx), int(win.height() * fy)))
        QCoreApplication.processEvents()
        from .screen_seen import state
        print(f"focus after a click in the {rest[0]}: inspect_screen says {state(bridge)['focus']!r}")
