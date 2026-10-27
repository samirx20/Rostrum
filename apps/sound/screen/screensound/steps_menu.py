"""Helpers of the scripted selection steps (steps_select.py): finding a QML item on screen, a key to the window, and the
real click on a settings-panel button (`bar-menu`)."""
from __future__ import annotations

from PySide6.QtGui import QKeySequence
from rostrum_gui.lazy_qtest import QTest   # never at import: a person's launch must not count as scripted (lazy_qtest.py)


def _find(item, prop):
    """The first item under `item` with a QML property `prop` (the Timeline: mixRows; the Editor: keysWidth)."""
    if item.property(prop) is not None:
        return item
    for child in item.childItems():
        found = _find(child, prop)
        if found is not None:
            return found
    return None


def _shown(item, name):
    """The visible item called `name` under `item` (kept-but-hidden delegates are skipped)."""
    if not item.isVisible():
        return None
    if item.objectName() == name and item.width() > 0:
        return item
    for child in item.childItems():
        found = _shown(child, name)
        if found is not None:
            return found
    return None


def _key(win, text):
    seq = QKeySequence(text)
    if seq.isEmpty():
        raise ValueError(f"key: {text!r} is not a key")
    combo = seq[0]
    QTest.keyClick(win, combo.key(), combo.keyboardModifiers())


def bar_menu(bridge, win, rest):
    """bar-menu Chord [Make_a_chord]: a real click on the panel's Chord ▾, a side menu open."""
    from PySide6.QtCore import QPoint, Qt
    button = None
    for _ in range(40):                   # the panel settles once the pointer is quiet (select_slots._settle)
        button = _shown(win.contentItem(), "actionBar:" + rest[0])
        if button is not None:
            break
        QTest.qWait(25)
    if button is None:
        raise RuntimeError(f"bar-menu: no {rest[0]} ▾ in the settings panel for this selection")
    QTest.qWait(100)                      # its row placed (the panel lays out the frame after)
    at = button.mapToScene(button.boundingRect().center())
    at = QPoint(int(at.x()), int(at.y()))
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    if len(rest) > 1:                     # the pointer rests on the side menu's row (it opens on hover)
        QTest.qWait(150)
        row = _shown(win.contentItem(), "menu:menu:" + rest[1].replace("_", " "))
        if row is None:
            names = []
            def walk(it):
                if it.objectName().startswith(("menu", "action")) and it.isVisible():
                    names.append(it.objectName())
                for c in it.childItems():
                    walk(c)
            walk(win.contentItem())
            raise RuntimeError(f"bar-menu: no {rest[1]} row in the {rest[0]} menu {names} {bridge.selectedIds}")
        at = row.mapToScene(row.boundingRect().center())
        QTest.mouseMove(win, QPoint(int(at.x()), int(at.y())))
        QTest.qWait(300)
