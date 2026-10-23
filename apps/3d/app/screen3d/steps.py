"""Scripted steps for screenshots and checks. Each goes through the same bridge (or viewport) call a click or drag makes.

    select <id> | frame <n> | set <param> <json value> | scrub <param> <v> <v> … | animate <param> (the key mark)
    keydrag <key id> <frame> | fold <id> | undo | redo | more | commands [query …] | run <command key> | play
    add <menu value, e.g. mesh:sphere | light:distant | camera | material | shot> | duplicate | delete
    wait <ms> | snap <png path> (a screenshot now, the run goes on)
    rail <shapes|lights|camera> (opens that flyout) | page build|animate|render | materials | shots | view (open the
    header's menus) | mouse <x> <y> (a click on the window) | renderstart | cancelrender (both don't wait)
    render (Cycles, the playhead frame; waits for the job, up to 10 min) | closerender
  Viewport (screen state, never the document): orbit <dx> <dy> | pan <dx> <dy> | zoom <steps> | mode shot|free
    exposure <stops> | studio <amount> | lights on|off | home | click <x> <y> (viewport pixels: selects what is there)
    look quick|final (Final: progressive Cycles in place; `wait` lets it refine)
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import json

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QPoint, Qt
from PySide6.QtTest import QTest

RENDER_WAIT_S = 600
VIEW = {"orbit": lambda v, a: v.orbit(float(a[0]), float(a[1])), "pan": lambda v, a: v.pan(float(a[0]), float(a[1])),
        "zoom": lambda v, a: v.zoom(float(a[0])), "mode": lambda v, a: v.setMode(a[0]),
        "exposure": lambda v, a: v.setExposure(float(a[0])), "studio": lambda v, a: v.setStudio(float(a[0])),
        "lights": lambda v, a: v.setSceneLights(a[0] == "on"), "home": lambda v, a: v.home(),
        "click": lambda v, a: v.click(float(a[0]), float(a[1])), "look": lambda v, a: v.setLook(a[0])}


def value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text            # a bare word is a string: set shape sphere


def do_step(bridge, win, step):
    word, *rest = step.split()
    if word == "select":
        bridge.select(rest[0])
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
    elif word in ("duplicate", "delete"):
        bridge.adder.duplicate() if word == "duplicate" else bridge.adder.remove()
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
        if not win.grabWindow().save(rest[0]):
            raise RuntimeError(f"step {step!r}: could not save {rest[0]}")
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
    elif word in VIEW:
        if bridge.viewport is None:
            raise RuntimeError(f"step {step!r}: no viewport")
        VIEW[word](bridge.viewport, rest)
    else:
        raise ValueError(f"unknown step {step!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
