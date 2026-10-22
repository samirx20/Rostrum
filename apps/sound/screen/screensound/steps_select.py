"""Scripted steps for the selection and its actions (screenshots and the flow walks). Each goes through the same
bridge call a click, a box, a key or a menu makes.

    select-many <id> <id> … | select-add <id> (Ctrl+click) | select-run <id> (Shift+click) | select-all [arrange|roll]
    box <track id>[,<track id>…] <t0> <t1>   (a box on the arrangement's lanes) | box roll <t0> <t1> <row0> <row1>
    range <t0> <t1> (a drag on the ruler) | range-clear
    action <key> (an action bar / menu entry: quantize, transpose_up, join, …; "sel:" may be left out)
    action-bar [arrange|roll] (that area has the focus; fails when the bar would be empty)
    menu <id> (the right-click menu on that item, open in the arrangement) | menu-roll <id> (in the Editor)
    key <sequence> (a key to the window: "Ctrl+D", "Q", "Shift+Up") | copy | cut | paste
    drag-many <dt s> [<d semitones>] [ctrl|shift|alt …] [to=<track>] (the selection, held by its first item, one
      gesture; to=: clips dragged onto that track's row)
    handle <id> start|end|fadeIn|fadeOut|level|stretch|length <dt s> [<dy row heights>] (a handle drag, one gesture)
    lock <track> (the header's lock: lock / unlock) | loop (Shift+L) | range-edge in|out (Shift+I / Shift+O)
    rename-open <id> (its name field, open) | rename <new name> (Enter in the open field) | open <id> (double-click: select + Editor)
    jump next|prev (`,` / `.`) | playhead-step <n> (Ctrl+arrows) | fit-selection (F)
    marker-add (M: a marker at the playhead, its name field open) | fit-bar <bar> (Land a bar here on the selected
      marker) | ask <action key> (its number field, open: for a picture) | place <design> (the Library's designed sound,
      double-clicked) | library <chip> (the Library open on a chip) | clean-open (the Clean up popover, open) |
      clean <voice 0|1> <noise 0|1> <echo 0|1> (Clean: the steps on the selected clips, then their cleaned takes)
"""
from __future__ import annotations

from PySide6.QtCore import Q_ARG, QMetaObject
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

WORDS = ("select-many", "select-add", "select-run", "select-all", "box", "range", "range-clear", "action",
         "action-bar", "menu", "menu-roll", "key", "copy", "cut", "paste", "drag-many", "handle", "lock", "loop",
         "range-edge", "rename-open", "rename", "open", "jump", "playhead-step", "fit-selection", "marker-add",
         "fit-bar", "ask", "place", "library", "clean-open", "clean")


def _find(item, prop):
    """The first item under `item` with a QML property `prop` (the Timeline: mixRows; the Editor: keysWidth)."""
    if item.property(prop) is not None:
        return item
    for child in item.childItems():
        found = _find(child, prop)
        if found is not None:
            return found
    return None


def _key(win, text):
    seq = QKeySequence(text)
    if seq.isEmpty():
        raise ValueError(f"key: {text!r} is not a key")
    combo = seq[0]
    QTest.keyClick(win, combo.key(), combo.keyboardModifiers())


def do_select_step(bridge, win, word, rest):
    if word == "select-many":
        bridge.selectMany(rest)
    elif word in ("select-add", "select-run"):
        bridge.clickSelect(rest[0], word == "select-add", word == "select-run")
    elif word == "select-all":
        bridge.focusArea(rest[0] if rest else "arrange")
        bridge.selectAll()
    elif word == "box":
        if rest[0] == "roll":
            bridge.focusArea("roll")
            bridge.boxRoll(float(rest[1]), float(rest[2]), float(rest[3]), float(rest[4]), False)
        else:
            bridge.boxSelect(rest[0].split(","), float(rest[1]), float(rest[2]), False)
        bridge.endBox()
    elif word == "range":
        bridge.setRange(float(rest[0]), float(rest[1]), False)
    elif word == "range-clear":
        bridge.clearRange()
    elif word == "action":
        bridge.runAction(rest[0] if rest[0].startswith(("sel:", "at:")) else f"sel:{rest[0]}")
    elif word == "action-bar":
        bridge.focusArea(rest[0] if rest else "arrange")
        if not bridge.actionBar():
            raise RuntimeError("action-bar: nothing to show for this selection")
    elif word in ("menu", "menu-roll"):
        host = _find(win.contentItem(), "mixRows" if word == "menu" else "keysWidth")
        if host is None:
            raise RuntimeError(f"{word}: the area is not on screen")
        QMetaObject.invokeMethod(host, "menuFor", Q_ARG("QVariant", rest[0]))
    elif word == "key":
        _key(win, rest[0])
    elif word in ("copy", "cut", "paste"):
        bridge.runAction(f"sel:{word}")
    elif word == "drag-many":
        ids = bridge.selectedIds
        if not ids or not bridge.beginDrag(ids[0]):
            raise RuntimeError(f"drag-many: nothing to drag: {bridge.status}")
        mods = set(rest[2:]) if len(rest) > 2 else set()
        dsemi = int(rest[1]) if len(rest) > 1 and not rest[1].startswith("to=") else 0
        dest = next((m[3:] for m in rest if m.startswith("to=")), "")
        if dest:
            bridge.dragTrack(dest)
        for f in (0.25, 0.5, 0.75, 1.0):
            bridge.dragTo(float(rest[0]) * f, round(dsemi * f), "ctrl" in mods, "shift" in mods, "alt" in mods, 0.05)
        bridge.endDrag()
    elif word == "handle":
        if not bridge.beginHandle(rest[0], rest[1]):
            raise RuntimeError(f"handle: {bridge.status}")
        dy = float(rest[3]) if len(rest) > 3 else 0.0
        for f in (0.5, 1.0):
            bridge.handleTo(float(rest[2]) * f, dy * f, False)
        bridge.endDrag()
    elif word == "lock":
        bridge.toggleLock(rest[0])
    elif word == "loop":
        bridge.toggleLoop()
    elif word == "range-edge":
        bridge.rangeEdge(rest[0])
    elif word == "rename-open":
        bridge.startRename(rest[0])
    elif word == "rename":                    # rename <new name>: Enter in the name field that is open
        if not bridge.renaming:
            raise RuntimeError("rename: no name field is open (rename-open <id>, marker-add or F2 first)")
        bridge.finishRename(bridge.renaming, " ".join(rest))
    elif word == "open":
        bridge.select(rest[0])
        bridge.workspace.setDock("editor")
    elif word == "jump":
        bridge.jump(1 if rest[0] == "next" else -1)
    elif word == "playhead-step":
        bridge.playheadStep(int(rest[0]))
    elif word == "fit-selection":
        bridge.fitSelection()
    elif word == "marker-add":
        bridge.markerAt(bridge.time)
    elif word == "fit-bar":
        bridge.runActionWith("sel:fit_bar", float(rest[0]))
    elif word == "ask":
        bar = _find(win.contentItem(), "menuOpen")
        item = next((i for i in bridge.actionBar() if i["key"] == f"sel:{rest[0]}"), None)
        if bar is None or item is None:
            raise RuntimeError(f"ask: no {rest[0]!r} on the context bar")
        QMetaObject.invokeMethod(bar, "press", Q_ARG("QVariant", item), Q_ARG("QVariant", bar.width() / 2))
    elif word == "place":
        from .adder import Adder
        if not Adder(bridge).add(f"design:{rest[0]}"):
            raise RuntimeError(f"place: {bridge.status}")
    elif word == "library":
        bridge.workspace.setLibrary(True)
        bridge.libraryWanted.emit(rest[0])
    elif word == "clean-open":
        bridge.cleanWanted.emit()
    elif word == "clean":
        voice, noise, echo = (r == "1" for r in rest[:3])
        if bridge.cleanSelected(voice, noise, echo):
            bridge.mix.cleaning.makeFor(bridge.selectedIds)
