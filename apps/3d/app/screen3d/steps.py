"""Scripted steps for screenshots and checks. Each goes through the same bridge (or viewport) call a click or drag makes.

    select <id> | selectmany <id> <id> … (the first is the base) | deselect (nothing selected: the Scene) | action <id> (a settings panel action, e.g. combine:subtract)
    preview <id> / unpreview (the hover preview of a panel action: what resting the pointer on it shows; leaving) | frame <n> | set <param> <json value> | scrub <param> <v> <v> … | animate <param> (the key mark)
    keydrag <key id> <frame> | fold <id> | undo | redo | more | commands [query …] | run <command key> | play
    context <item id | -> (the right-click menu)
    add <menu value, e.g. mesh:sphere | light:distant | camera | material | shot> | duplicate | delete
    arm <mesh:box …> [field=value …] (a shape picked in the Shapes or Type & logo flyout, with its source for a logo:
    svgFile=<path> or doc2d=<id> layer=<id>; the next viewport click (`mouseclick`, `viewclick`) places it on the surface there)
    type <words …> (real keys into a 3D text just placed: live, one undo step) | typeend (Esc ends the typing)
    (a click in the viewport by real input: the kit's `mouseclick <x> <y>`, window pixels)
    drawings (From a 2D drawing's list of 2D items) | drawing <doc2d> (its path layers: the list's second level)
    wait <ms> | snap <png path> (a screenshot now, the run goes on)
    rail <shapes|type|lights|camera> (opens that flyout) | page build|animate|render | materials | shots | view (open the
    header's menus) | mouse <x> <y> (a click on the window) | renderstart | cancelrender (both don't wait)
    render (Cycles, the playhead frame; waits for the job, up to 10 min) | closerender
  Viewport (screen state, never the document): orbit <dx> <dy> | pan <dx> <dy> | zoom <steps> | mode shot|free
    exposure <stops> | studio <amount> | lights on|off | home | viewclick <x> <y> (viewport pixels: selects what is there, or places the armed shape;
    named apart from the kit's `click <text>`, which runs first)
    look quick|final (Final: progressive Cycles in place; `wait` lets it refine)
  Gizmo (real mouse input on the window): gizmo-drag <handle: move0..2 | plane | turn0..2 | scale0..2> <dx> <dy> [ctrl]
    (press on that handle, move by dx dy screen px in 8 steps, release) | gizmo-show all|move|turn|scale | key-moved
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import json

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QObject, QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from rostrum_gui.settle import save_snap

RENDER_WAIT_S = 600
VIEW = {"orbit": lambda v, a: v.orbit(float(a[0]), float(a[1])), "pan": lambda v, a: v.pan(float(a[0]), float(a[1])),
        "zoom": lambda v, a: v.zoom(float(a[0])), "mode": lambda v, a: v.setMode(a[0]),
        "exposure": lambda v, a: v.setExposure(float(a[0])), "studio": lambda v, a: v.setStudio(float(a[0])),
        "lights": lambda v, a: v.setSceneLights(a[0] == "on"), "home": lambda v, a: v.home(),
        "viewclick": lambda v, a: v.click(float(a[0]), float(a[1])), "look": lambda v, a: v.setLook(a[0])}


def value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text            # a bare word is a string: set shape sphere


def do_step(bridge, win, step):
    word, *rest = step.split()
    if word == "select":
        bridge.select(rest[0])
    elif word == "deselect":
        bridge.select("")
    elif word == "selectmany":
        bridge.selectMany(rest)
    elif word == "action":
        bridge.actions.run(rest[0])
    elif word == "preview":
        bridge.actions.previewStart(rest[0])
    elif word == "unpreview":
        bridge.actions.previewEnd()
    elif word == "frame":
        bridge.setFrame(int(rest[0]))
    elif word == "set":
        bridge.setValue(rest[0], value(" ".join(rest[1:])))
    elif word == "scrub":
        for v in rest[1:]:
            bridge.scrub(rest[0], value(v))
        bridge.endScrub()
    elif word == "animate":
        bridge.toggleAnimate(rest[0])
    elif word == "keydrag":
        if not bridge.beginKeyDrag(rest[0]):
            raise RuntimeError(f"step {step!r}: {bridge.status}")
        bridge.keyDragTo(float(rest[1]))
        bridge.endDrag()
    elif word == "fold":
        bridge.toggleFold(rest[0])
    elif word in ("undo", "redo"):
        getattr(bridge, word)()
    elif word == "more":
        bridge.toggleMore()
    elif word == "play":
        bridge.togglePlay()
    elif word == "commands":
        QMetaObject.invokeMethod(win, "openCommands", Q_ARG("QVariant", " ".join(rest)))
    elif word == "run":
        bridge.run(rest[0])
    elif word == "add":
        bridge.adder.add(rest[0])
    elif word == "arm":            # arm <choice> [field=value …]: a flyout's pick; the next viewport click (`mouseclick`, `viewclick`) places it
        extra = dict(a.split("=", 1) for a in rest[1:])
        bridge.adder.armWith(rest[0], extra) if extra else bridge.adder.arm(rest[0])
    elif word == "type":           # real keys into the cursor in the viewport
        words, typer = step.split(None, 1)[1] if rest else "", bridge.adder.typer
        for ch in words:
            _key(win, Qt.Key(ord(ch.upper())) if ch.isalnum() else Qt.Key_unknown, ch)
        if typer.text != words:
            raise RuntimeError(f"type: the keys did not reach the text being typed (it has {typer.text!r})")
    elif word == "typeend":        # Esc ends the typing (the keys' own way)
        _key(win, Qt.Key_Escape, "")
        if bridge.adder.typer.item:
            raise RuntimeError("typeend: Esc did not end the typing")
    elif word == "drawings":
        QMetaObject.invokeMethod(win, "openDrawings")
    elif word == "drawing":
        QTest.qWait(300)
        menu = win.findChild(QObject, "drawings2d")
        if menu is None:
            raise RuntimeError("drawing: the 2D drawings list is not there")
        QMetaObject.invokeMethod(menu, "picked", Q_ARG(str, rest[0]))
    elif word in ("duplicate", "delete"):
        bridge.adder.duplicate() if word == "duplicate" else bridge.adder.remove()
    elif word == "context":        # context <item id | -> : the right-click menu for that item (- = empty space)
        QMetaObject.invokeMethod(win, "openContext", Q_ARG("QVariant", "" if rest[0] == "-" else rest[0]))
    elif word == "rail":
        QMetaObject.invokeMethod(win, "openRailGroup", Q_ARG("QVariant", rest[0]))
    elif word == "page":
        bridge.setPage(rest[0])
    elif word in ("materials", "shots", "view"):
        QMetaObject.invokeMethod(win, "open" + word.capitalize())
    elif word == "mouse":
        QTest.qWait(400)                              # let the last step lay out
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(int(rest[0]), int(rest[1])))
    elif word == "wait":
        QTest.qWait(int(rest[0]))
    elif word == "snap":
        v = bridge.viewport
        save_snap(win, rest[0], may_move=bool((v and v.final.on) or getattr(bridge, "playing", False)),            # the shared snap: waits for the newest picture
                  ready=(lambda: v.serial > 0 and v._r.idle() and not v._next.isActive()) if v else None)
    elif word == "renderstart":
        bridge.renderStill()
    elif word == "cancelrender":
        bridge.render.cancel()
    elif word == "render":
        bridge.renderStill()
        if not bridge.render.wait(RENDER_WAIT_S):
            raise RuntimeError(f"step {step!r}: the render did not finish in {RENDER_WAIT_S} s")
        QCoreApplication.processEvents()          # deliver the job's result to the GUI thread
        if bridge.render.state != "done":
            raise RuntimeError(f"step {step!r}: {bridge.render.note}")
    elif word == "closerender":
        bridge.render.dismiss()
    elif word == "gizmo-drag":
        _gizmo_drag(bridge, win, rest[0], float(rest[1]), float(rest[2]), "ctrl" in rest[3:])
    elif word == "gizmo-show":
        bridge.viewport.gizmo.setShow(rest[0])
    elif word == "key-moved":
        bridge.viewport.gizmo.keyMoved()
    elif word in VIEW:
        if bridge.viewport is None:
            raise RuntimeError(f"step {step!r}: no viewport")
        VIEW[word](bridge.viewport, rest)
    else:
        raise ValueError(f"unknown step {step!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {step!r}: {bridge.status}")


def _key(win, key, text):
    """A key press and release with its text, sent to the window (what the keyboard sends)."""
    from PySide6.QtGui import QKeyEvent
    for kind in (QKeyEvent.Type.KeyPress, QKeyEvent.Type.KeyRelease):
        QCoreApplication.sendEvent(win, QKeyEvent(kind, key, Qt.NoModifier, text))
    QCoreApplication.processEvents()


def _gizmo_drag(bridge, win, handle, dx, dy, ctrl):
    """Press on a gizmo handle (its end; a ring at its first point), drag by (dx, dy) screen px, release: real input."""
    from PySide6.QtQuick import QQuickItem
    QTest.qWait(600)                                          # the picture and the handles land
    QCoreApplication.processEvents()
    hs = {h["id"]: h for h in bridge.viewport.gizmo.handles}
    if handle not in hs:
        raise RuntimeError(f"gizmo-drag: no handle {handle!r} (there are: {', '.join(hs) or 'none'})")
    h, vp = hs[handle], win.findChild(QQuickItem, "viewport3d")
    fx, fy = h["points"][6] if "points" in h else h["b"]   # a ring: 45° round, off where rings cross
    at = vp.mapToScene(QPointF(fx * vp.width(), fy * vp.height()))
    mods = Qt.ControlModifier if ctrl else Qt.NoModifier
    start = QPoint(round(at.x()), round(at.y()))
    QTest.mouseMove(win, start)
    QTest.mousePress(win, Qt.LeftButton, mods, start)
    for k in range(1, 9):
        QTest.mouseMove(win, QPoint(round(at.x() + dx * k / 8), round(at.y() + dy * k / 8)))
        QTest.qWait(30)
    QTest.mouseRelease(win, Qt.LeftButton, mods, QPoint(round(at.x() + dx), round(at.y() + dy)))
