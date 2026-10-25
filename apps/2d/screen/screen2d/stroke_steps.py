"""Scripted steps for picking colours, selecting strokes and the focused area (paint_steps.py hands these over); each goes
through the calls the pointer and keys make.

    altpick <x> <y> [click]        hold Alt with the pointer at (x, y) (composition px): the swatch shows the colour there;
                                   `click` picks it as the brush colour. `altoff` lets go of Alt
    lasso <x,y> <x,y> … [open]     Ctrl+drag a lasso (composition px); `open` leaves it undrawn-to-the-end (a picture of it)
    selectstrokes on|off           the bar's Select strokes (the next drag is a lasso)
    strokesmove <dx> <dy>          drag the picked strokes by that much | strokesturn <deg> [scale] | strokesdelete |
    strokescopy | strokespaste | strokesclear (Esc)
    strokeshandle scale|turn <x> <y> [steps]    drag a corner handle / the turn knob to (x, y) (composition px); steps = Shift
    grabhandle scale|turn <x> <y>  the same with the real pointer: press on the handle where it is drawn, drag, release
    clickarea canvas|timeline|settings    a real click in that part of the window (the focused area follows it)
    key <combo>                    a real key press (B, V, Escape, Ctrl+C) | keydown Alt | keyup Alt (held across steps)
    cmove <x> <y>                  move the real pointer there (a hover)
    cclick <x> <y> | cpath [ctrl] <x,y> <x,y> …    a real mouse click / press-drag-release at composition px (the canvas's
                                   own mapping to the window); ctrl holds Ctrl for the drag
    reston <text>                   rest the pointer on the visible item with that text (hover help shows after 0.9 s)
    clickbtn <label>               a real click on the context-bar button with that label
    clickstarts <text>             the same for an item whose text starts with that (a name that changes)
    clicktext <text>               a real click on the visible item whose text or label is that (menus, buttons)
    dragtext <dy> <text>           a real press on that item, dragged dy window px up (-) or down, released (a paint layer's row)
    shot <png>                     wait for the newest frame, then save a picture of the window (a walk takes one per step)
    windowsize <W>x<H>             resize the window now (a picture of an open menu needs the final size before it opens)
    barbutton <label>              open that context-bar button's ▾ menu (Set depth)
    clickat <x> <y>                a real click at that window point (logical px) | dclickat <x> <y>: a real double-click there
"""
from __future__ import annotations
from rostrum_gui.pointer import wait  # never QTest.qWait: it starves the worker threads

from PySide6.QtCore import Q_ARG, QObject, QCoreApplication, QMetaObject, QPoint, QPointF, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from rostrum_gui.settle import save_snap

WORDS = ("altpick", "altoff", "lasso", "selectstrokes", "strokesmove", "strokesturn", "strokeshandle", "grabhandle", "strokesdelete", "strokescopy",
         "strokespaste", "strokesclear", "clickarea", "clickat", "dclickat", "barbutton", "windowsize", "key", "keydown", "keyup", "cclick", "cpath", "clickbtn", "clickname", "clicktext", "clickstarts", "dragtext", "reston", "shot", "cmove")

# where an empty spot of each area is, as fractions of the window (width, height)
AREAS = {"canvas": (0.45, 0.30), "timeline": (0.60, 0.93), "settings": (0.93, 0.55)}


def _walk(item):
    todo = [item]
    while todo:
        o = todo.pop()
        yield o
        todo.extend(o.childItems())


def _scene_of(win, x, y):
    """Composition px -> window px, through the canvas's own mapping (Stage.qml compOrigin / compScale)."""
    stage = win.findChild(QObject, "stage")
    o, k = stage.property("compOrigin"), stage.property("compScale")
    c = stage.mapToScene(QPointF(o.x() + x * k, o.y() + y * k))
    return QPoint(int(c.x()), int(c.y()))


def _plain(v):
    """A text with its runs of spaces made one (a label may keep two for looks)."""
    return " ".join(v.split()) if isinstance(v, str) else v


def _in_tip(o):
    """Inside a hover tip (the kit's HoverTip popup): it only names what the pointer rests on, never a click target."""
    while o is not None:
        owner = o.parent()
        if owner is not None and owner.metaObject().className().startswith("HoverTip"):
            return True
        o = o.parentItem()
    return False


def _find(win, text, prefix=False):
    """The visible item showing `text` (its text or its label), topmost first; hover tips left out."""
    todo, hits = [i for i in (win.contentItem(), win.property("overlay")) if i is not None], []     # the overlay holds open menus
    while todo:
        o = todo.pop()
        if o.isVisible() and o.width() > 0:
            m = o.property("modelData")
            m = m.toVariant() if hasattr(m, "toVariant") else m
            names = [_plain(v) for v in (o.property("text"), o.property("label"), *((m.get("label"), m.get("text")) if isinstance(m, dict) else ()))]
            if (text in names or (prefix and any(isinstance(n, str) and n.startswith(text) for n in names))) and not _in_tip(o):
                hits.append(o)
        todo.extend(o.childItems())
    return hits


def _texts(win, word):
    todo, out = [i for i in (win.contentItem(), win.property("overlay")) if i is not None], []
    while todo:
        o = todo.pop()
        for k in ("text", "label"):
            v = o.property(k)
            if isinstance(v, str) and word.lower() in v.lower():
                out.append(f"{k}={v!r} visible={o.isVisible()} w={o.width():.0f} {o.metaObject().className()}")
        todo.extend(o.childItems())
    return out[:8]


def _click_item(win, o):
    wait(120)        # let a bar or menu rebuilt by the last step be laid out first: read its place after, as a person sees it
    c = o.mapToScene(QPointF(o.width() / 2, o.height() / 2))
    QTest.mouseMove(win, QPoint(int(c.x()), int(c.y())))
    wait(80)
    at = QPoint(int(c.x()), int(c.y()))
    QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at)
    wait(90)
    QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at)
    wait(400)


def _named(item, name):
    """The first shown item called `name` in the drawn tree (childItems), or None."""
    if not item.isVisible():
        return None
    if item.objectName() == name:
        return item
    return next((hit for c in item.childItems() if (hit := _named(c, name)) is not None), None)


def do_stroke_step(bridge, win, word, rest, step):
    pick, sel = bridge.colourPick, bridge.strokeSelect
    if word == "shot":
        for _ in range(100):
            if bridge.frames.idle() and bridge.frame > 0:
                break
            wait(100)
        wait(700)
        if bridge.status.startswith("Error"):
            raise RuntimeError(bridge.status)
        save_snap(win, rest[0], ready=bridge.frames.idle)
        print("saved", rest[0], "| status:", bridge.status)
    elif word == "key":
        keys = QKeySequence(rest[0])[0]
        QTest.keyClick(win, Qt.Key(keys.key()), keys.keyboardModifiers())
        wait(150)
    elif word in ("keydown", "keyup"):
        held = {"Ctrl": Qt.Key.Key_Control, "Shift": Qt.Key.Key_Shift, "Alt": Qt.Key.Key_Alt}.get(rest[0]) or Qt.Key(QKeySequence(rest[0])[0].key())
        (QTest.keyPress if word == "keydown" else QTest.keyRelease)(win, held)
        wait(100)
    elif word == "cmove":
        QTest.mouseMove(win, _scene_of(win, float(rest[0]), float(rest[1])))
        wait(250)
    elif word == "cclick":
        p = _scene_of(win, float(rest[0]), float(rest[1]))
        QTest.mouseMove(win, p)
        wait(80)
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
        wait(250)
    elif word == "cpath":
        mod = Qt.KeyboardModifier.ControlModifier if rest[0] == "ctrl" else Qt.KeyboardModifier.NoModifier
        pts = [_scene_of(win, *(float(v) for v in a.split(","))) for a in rest if a != "ctrl"]
        QTest.mouseMove(win, pts[0])
        wait(60)
        QTest.mousePress(win, Qt.MouseButton.LeftButton, mod, pts[0])
        for a, b in zip(pts, pts[1:]):
            for k in range(1, 5):
                QTest.mouseMove(win, QPoint(a.x() + (b.x() - a.x()) * k // 4, a.y() + (b.y() - a.y()) * k // 4))
                QCoreApplication.processEvents()
        QTest.mouseRelease(win, Qt.MouseButton.LeftButton, mod, pts[-1])
        wait(300)
    elif word == "reston":
        wait(700)                     # the window has settled (the top bar slides in at start)
        hits = _find(win, " ".join(rest))
        if not hits:
            raise RuntimeError(f"step {step!r}: nothing visible is called {' '.join(rest)!r}")
        c = hits[0].mapToScene(QPointF(hits[0].width() / 2, hits[0].height() / 2))
        QTest.mouseMove(win, QPoint(int(c.x()) - 6, int(c.y())))
        QTest.mouseMove(win, QPoint(int(c.x()), int(c.y())))
        wait(900)
    elif word in ("clickbtn", "clicktext", "clickstarts"):
        hits = _find(win, " ".join(rest), prefix=word == "clickstarts")
        if not hits:
            raise RuntimeError(f"step {step!r}: nothing visible is called {' '.join(rest)!r}; near it: {_texts(win, rest[0])}")
        _click_item(win, hits[0])
    elif word == "clickname":                      # clickname <objectName>: a control that has no words (the Effects row's +)
        found = win.findChild(QObject, rest[0]) or _named(win.contentItem(), rest[0])   # a Repeater's items: only in the drawn tree
        if found is None:
            raise RuntimeError(f"step {step!r}: nothing on screen is named {rest[0]!r}")
        _click_item(win, found)
    elif word == "dragtext":
        hits = _find(win, " ".join(rest[1:]))
        if not hits:
            raise RuntimeError(f"step {step!r}: nothing visible is called {' '.join(rest[1:])!r}")
        c = hits[0].mapToScene(QPointF(hits[0].width() / 2, hits[0].height() / 2))
        a, dy = QPoint(int(c.x()), int(c.y())), int(rest[0])
        QTest.mouseMove(win, a)
        wait(60)
        QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
        for k in range(1, 9):
            QTest.mouseMove(win, QPoint(a.x(), a.y() + dy * k // 8))
            wait(20)
        QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(a.x(), a.y() + dy))
        wait(300)
    elif word == "altpick":
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
    elif word == "strokeshandle":
        if not sel.drag_handle(rest[0], (float(rest[1]), float(rest[2])), rest[3:4] == ["steps"]):
            raise RuntimeError(f"step {step!r}: no strokes picked")
    elif word == "grabhandle":
        from .stroke_geom import handle_point
        if not sel.box:
            raise RuntimeError(f"step {step!r}: no strokes picked")
        zoom = win.findChild(QObject, "stage").property("compScale")
        a, b = handle_point(rest[0], sel.box, zoom, sel.knobBelow), (float(rest[1]), float(rest[2]))
        pts = [_scene_of(win, a[0] + (b[0] - a[0]) * k / 8, a[1] + (b[1] - a[1]) * k / 8) for k in range(9)]
        QTest.mouseMove(win, pts[0])
        wait(60)
        QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pts[0])
        for q in pts[1:]:
            QTest.mouseMove(win, q)
            wait(20)
        QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pts[-1])
        wait(300)
        if bridge.status not in ("Scale strokes", "Turn strokes"):
            raise RuntimeError(f"step {step!r}: the drag did not take the handle (status: {bridge.status})")
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
            wait(60)
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
                wait(400)                    # the menu opens with a short reveal
                break
            todo.extend(o.childItems())
        else:
            raise RuntimeError(f"step {step!r}: no context-bar button called {label!r}")
    elif word == "clickat":
        QTest.mouseMove(win, QPoint(int(rest[0]), int(rest[1])))        # the pointer arrives first, as a hand's does
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(rest[0]), int(rest[1])))
        QCoreApplication.processEvents()
    elif word == "dclickat":
        p = QPoint(int(rest[0]), int(rest[1]))
        QTest.mouseMove(win, p)
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
        QTest.mouseDClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
        QCoreApplication.processEvents()
        wait(150)
    elif word == "clickarea":
        fx, fy = AREAS[rest[0]]
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(win.width() * fx), int(win.height() * fy)))
        QCoreApplication.processEvents()
        from .screen_seen import state
        print(f"focus after a click in the {rest[0]}: inspect_screen says {state(bridge)['focus']!r}")
