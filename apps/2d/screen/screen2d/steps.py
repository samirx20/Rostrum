"""Scripted steps for screenshots and checks. Each goes through the same bridge call a click or drag makes.

    select <id> | page design|animate | time <s> | set <param> <json value> | scrub <param> <v> <v> …
    animate <param> (the key mark's toggle) | drag <layer> <dx> <dy> (canvas drag, composition px)
    keydrag <key id> <t> | open <layer> (timeline rows) | fold <layer> (layers panel) | pick <x> <y>
    undo | redo | more | commands [query …] | run <command key> | play
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import json

from PySide6.QtCore import Q_ARG, QMetaObject


def value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text            # a bare word is a string: set align left


def do_step(bridge, win, step):
    word, *rest = step.split()
    if word == "select":
        bridge.select(rest[0])
    elif word == "page":
        bridge.setPage(rest[0])
    elif word == "time":
        bridge.setTime(float(rest[0]))
    elif word == "set":
        bridge.setValue(rest[0], value(" ".join(rest[1:])))
    elif word == "scrub":
        for v in rest[1:]:
            bridge.scrub(rest[0], value(v))
        bridge.endScrub()
    elif word == "animate":
        bridge.toggleAnimate(rest[0])
    elif word == "drag":
        bridge.select(rest[0])
        if not bridge.beginMove():
            raise RuntimeError(f"step {step!r}: nothing to move")
        dx, dy = float(rest[1]), float(rest[2])
        for f in (0.25, 0.5, 0.75, 1.0):             # a few moves, as a hand would make
            bridge.moveBy(dx * f, dy * f)
        bridge.endDrag()
    elif word == "keydrag":
        bridge.beginKeyDrag(rest[0])
        bridge.keyDragTo(float(rest[1]))
        bridge.endDrag()
    elif word == "open":
        bridge.toggleTrack(rest[0])
    elif word == "fold":
        bridge.toggleFold(rest[0])
    elif word == "pick":
        bridge.pickAt(float(rest[0]), float(rest[1]))
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
    else:
        raise ValueError(f"unknown step {step!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
