"""Scripted steps for screenshots and checks. Each goes through the same bridge call a click or drag makes.

    page instruments|timeline|mix | select <id> | time <s> | set <param> <json value>
    drag-note <id> <dt s> <d semitones> | drag-clip <id> <dt s> | drag-marker <id> <dt s> |
    drag-section <id> <dt s> (it and everything inside: section.move)   (one gesture each)
    add-note <t s> <midi key> | delete | mute <track> | solo <track>
    arm <track> | record (start / stop, the real microphone) | record-fake <source.wav> (TEST SEAM: a WAV stands in
    for the microphone; the take stays running for the shot)
    undo | redo | play | render (wait for the newest render) | more | commands [query …] | run <command key> |
    wait <seconds>
    zoom <factor> | scroll <s> | fit | lane <track> <lane> | lane-point <track> <t> <v> [<t2> <v2>] | lane-delete |
    picture <file|none>     (see steps_view.py)
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject

from .steps_view import WORDS as VIEW_WORDS, do_view_step

RENDER_WAIT_S = 120


def value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text            # a bare word is a string: set tone warm


def drag(bridge, item_id, dt, dsemi=0):
    if not bridge.beginDrag(item_id):
        raise RuntimeError(f"drag: can't move {item_id!r}: {bridge.status}")
    for f in (0.25, 0.5, 0.75, 1.0):             # a few moves, as a hand would make
        bridge.dragBy(dt * f, round(dsemi * f), False)
    bridge.endDrag()


def wait_render(bridge):
    """Let the debounce fire and the newest render land (or fail, loudly)."""
    end = time.monotonic() + RENDER_WAIT_S
    while bridge.transport.busy():
        if time.monotonic() > end:
            raise RuntimeError(f"render: nothing after {RENDER_WAIT_S} s")
        QCoreApplication.processEvents()
        time.sleep(0.02)
    if bridge.soundState.startswith("Render failed"):
        raise RuntimeError(f"render failed: {bridge.status}")


def do_step(bridge, win, step, recorder=None):
    word, *rest = step.split()
    if word == "page":
        bridge.setPage(rest[0])
    elif word == "select":
        bridge.select(rest[0])
    elif word == "time":
        bridge.setTime(float(rest[0]))
    elif word == "set":
        bridge.setValue(rest[0], value(" ".join(rest[1:])))
    elif word == "drag-note":
        drag(bridge, rest[0], float(rest[1]), int(rest[2]) if len(rest) > 2 else 0)
    elif word in ("drag-clip", "drag-marker", "drag-section"):
        drag(bridge, rest[0], float(rest[1]))
    elif word == "add-note":
        bridge.addNote(float(rest[0]), int(rest[1]))
    elif word == "delete":
        bridge.removeSelected()
    elif word in ("mute", "solo"):
        bridge.toggleTrack(rest[0], word)
    elif word == "arm":
        recorder.arm(rest[0])
    elif word == "record":
        recorder.toggleRecord()
    elif word == "record-fake":
        recorder.command = [sys.executable, "-I", str(Path(__file__).with_name("fake_mic.py")), "{out}", rest[0]]
        recorder.toggleRecord()
        for _ in range(15):                     # let a second of levels arrive
            QCoreApplication.processEvents()
            time.sleep(0.1)
    elif word in VIEW_WORDS:
        do_view_step(bridge, word, rest)
    elif word in ("undo", "redo"):
        getattr(bridge, word)()
    elif word == "play":
        bridge.togglePlay()
    elif word == "render":
        wait_render(bridge)
    elif word == "more":
        bridge.toggleMore()
    elif word == "commands":
        QMetaObject.invokeMethod(win, "openCommands", Q_ARG("QVariant", " ".join(rest)))
    elif word == "run":
        bridge.run(rest[0])
    elif word == "wait":                      # let background work (the listen pictures) land: wait <seconds>
        end = time.monotonic() + float(rest[0])
        while time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.02)
    else:
        raise ValueError(f"unknown step {step!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
