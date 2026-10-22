"""Scripted steps for screenshots and checks. Each goes through the same bridge call a click or drag makes.

    page instruments|timeline|mix | select <id> | time <s> | set <param> <json value>
    drag-note <id> <dt s> <d semitones> | drag-clip <id> <dt s> | drag-marker <id> <dt s> | drag-project-marker <name> <dt s> |
    drag-section <id> <dt s> (it and everything inside: section.move) | drag-tempo <id> <dt s> | drag-key <id> <dt s> |
    drag-edge <section id> at|end <dt s>   (one gesture each)
    song <start_bpm|add_tempo|set_key|add_key|add_section> [<value>] | song-open (the Song popup) |
    choice-open <text shown> (a choice list, open) | picture-start <marker name|none> | picture-link <item id> | picture-pick (the project list, open)
    add-note <t s> <midi key> | delete | mute <track> | solo <track>
    arm <track> | record (start / stop, the real microphone) | record-fake | take-panel | take-set | punch | midi-fake |
    keys (steps_record.py)
    undo | redo | play | render (wait for the newest render) | more | commands [query …] | run <command key> |
    wait <seconds>
    zoom <factor> | scroll <s> | fit | lane <track> <lane> | lane-point <track> <t> <v> [<t2> <v2>] | lane-delete |
    picture <file|none>     (see steps_view.py)
    deliver <streaming|apple|ebu|atsc|podcast> (master target, one change) | export-as <format> [<rate> [trim|full]] | export (Render mix and stems, waits) |
    clean-take (Make cleaned take on the selected clip, waits) | model-panel (the download question, for a screenshot) |
    duck-add <track> <under track> | duck-open <duck id> | duck-set <param> <json value> (the open duck)
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import json
import time

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject

from .steps_record import WORDS as RECORD_WORDS, do_record_step
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


def wait_job(job, start, what):
    """Start a background job (Render mix and stems, Make cleaned take) and wait for it to land (or fail, loudly)."""
    if not start():
        raise RuntimeError(f"{what}: {job.status or 'did not start'}")
    end = time.monotonic() + 3 * RENDER_WAIT_S
    while job.busy:
        if time.monotonic() > end:
            raise RuntimeError(f"{what}: nothing after {3 * RENDER_WAIT_S} s")
        QCoreApplication.processEvents()
        time.sleep(0.02)
    if job.status.startswith("Error"):
        raise RuntimeError(job.status)


def do_mix_step(mix, word, rest):
    if word == "deliver":
        mix.loudness.choose(rest[0])
    elif word == "export-as":                # export-as <format> [<sample rate>] [trim|full]: what the next export saves as
        mix.export.setFormat(rest[0])
        if len(rest) > 1:
            mix.export.setRate(rest[1])
        mix.export.setTrim(rest[2:3] != ["full"])
    elif word == "export":
        wait_job(mix.export, mix.export.start, "export")
    elif word == "clean-take":
        wait_job(mix.cleaning, mix.cleaning.make, "cleaned take")
    elif word == "model-panel":
        from rostrum_sound.cleanup import models
        mix.cleaning.download.ask([models.UMXHQ, models.DFN3])
    elif word == "model-download":            # press Download on the open model question; wait for it to end
        d = mix.cleaning.download
        d.start()
        end = time.monotonic() + 3 * RENDER_WAIT_S
        while d.state == "downloading" and time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.02)
    elif word == "duck-add":
        mix.ducks.add(rest[0], rest[1])
    elif word == "duck-open":
        mix.ducks.select(rest[0])
    elif word == "duck-set":
        mix.ducks.setValue(rest[0], value(" ".join(rest[1:])))


MIX_WORDS = ("deliver", "export-as", "export", "clean-take", "model-panel", "model-download", "duck-add", "duck-open", "duck-set")


def find_choice(item, shown):
    """The first visible choice field (the kit's ChoiceField) that shows `shown`."""
    if (item.isVisible() and item.property("options") is not None and item.property("current") is not None
            and item.property("text") == shown):
        return item
    for child in item.childItems():
        found = find_choice(child, shown)
        if found is not None:
            return found
    return None


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
    elif word in ("drag-clip", "drag-marker", "drag-section", "drag-tempo", "drag-key"):
        drag(bridge, rest[0], float(rest[1]))
    elif word == "drag-edge":                 # drag-edge <section id> at|end <dt s>
        bridge.beginEdge(rest[0], rest[1])
        for f in (0.5, 1.0):
            bridge.dragBy(float(rest[2]) * f, 0, False)
        bridge.endDrag()
    elif word == "song":                      # song <start_bpm|add_tempo|set_key|add_key|add_section> [<value>]
        bridge.songDo(rest[0], " ".join(rest[1:]))
    elif word == "song-open":                 # the Song popup, open (for a screenshot)
        QMetaObject.invokeMethod(win, "openSong")
    elif word == "picture-link":              # picture-link <item id> (a 2D item's newest render)
        bridge.linkPicture(rest[0])
    elif word == "choice-open":              # choice-open <the words a choice field shows now>: its list, open (for a screenshot)
        field = find_choice(win.contentItem(), rest and " ".join(rest))
        if field is None:
            raise RuntimeError(f"step {step!r}: no choice showing that")
        QMetaObject.invokeMethod(field, "open")
    elif word == "picture-pick":             # the corner's "From the project…" list, open (for a screenshot)
        QMetaObject.invokeMethod(win, "openPicturePick")
    elif word == "drag-project-marker":      # drag-project-marker <name> <dt s>: the marker band's release
        mid = next(m["id"] for m in bridge.markers if m["name"] == rest[0] and m["shared"])
        if not bridge.moveSharedMarker(mid, float(rest[1]), True):
            raise RuntimeError(f"step {step!r}: the marker didn't move")
    elif word == "picture-start":            # picture-start <marker name>|none
        bridge.setPictureStart("" if rest[0] == "none" else rest[0])
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
    elif word in RECORD_WORDS:
        do_record_step(recorder, word, rest)
    elif word in VIEW_WORDS:
        do_view_step(bridge, word, rest)
    elif word in MIX_WORDS:
        do_mix_step(bridge.mix, word, rest)
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
