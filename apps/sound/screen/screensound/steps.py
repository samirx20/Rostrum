"""Scripted steps for screenshots and checks. Each goes through the same bridge call a click or drag makes.

    dock editor|mixer|none | page timeline|mix|instruments (old scripts: = dock editor|mixer|none) | select <id> | time <s> | set <param> <json value>
    drag-note <id> <dt s> <d semitones> | drag-clip <id> <dt s> | drag-marker <id> <dt s> | drag-project-marker <name> <dt s> |
    drag-section <id> <dt s> (it and everything inside: section.move) | drag-tempo <id> <dt s> | drag-key <id> <dt s> |
    drag-edge <section id> at|end <dt s>   (one gesture each)
    song <start_bpm|add_tempo|set_key|add_key|add_section> [<value>] | song-open (the song, in the settings panel) |
    choice-open <text shown> (a choice list, open) | picture-start <marker name|none> | picture-link <item id> | picture-pick (the project list, open)
    add-note <t s> <midi key> | delete | mute <track> | solo <track>
    arm <track> | record (start / stop, the real microphone) | record-fake | take-panel | take-set | punch | midi-fake |
    keys (steps_record.py)
    undo | redo | play | render (wait for the newest render) | more | commands [query …] | run <command key> |
    wait <seconds> | shot <file.png> (a picture of the window now; several per run) | agent <label>|<json calls> |
    select-last <n> | handle-first <part> <dt s> (the walks: the items just made, their handle)
    zoom <factor> | scroll <s> | fit | lane <track> <lane> | lane-point <track> <t> <v> [<t2> <v2>] | lane-delete |
    picture <file|none>     (see steps_view.py)
    deliver <streaming|apple|ebu|atsc|podcast> (master target, one change) | export-as <format> [<rate> [trim|full]] | export-more [<target> [<format>]] (+ Another version) | export-what <all|range|section:<id>> | export (the Export sheet's Export, waits) |
    clean-take (Make cleaned take on the selected clip, waits) | model-panel (the download question, for a screenshot) |
    duck-add <track> <under track> | duck-open <duck id> | duck-set <param> <json value> (the open duck)
    select-many, select-add, select-run, select-all, box, range, action, action-bar, menu, menu-roll, key, copy, cut,
    paste, drag-many (the selection and its actions: steps_select.py)
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import json
import time

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject

from .steps_record import WORDS as RECORD_WORDS, do_record_step
from .steps_select import WORDS as SELECT_WORDS, do_select_step
from .steps_swap import WORDS as SWAP_WORDS, do_swap_step
from .steps_view import WORDS as VIEW_WORDS, do_view_step
from .workspace import OLD_PAGES

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
    elif word == "export":                     # the Export sheet's Export (the kit's flow: asks when a file is there)
        exp = mix.export
        exp.request()
        if exp.asking():
            raise RuntimeError("export: a file of that name is already there (answer with the kit's `exportnow both`)")
        if exp.state == "running" and not exp.wait(3 * RENDER_WAIT_S):
            raise RuntimeError(f"export: nothing after {3 * RENDER_WAIT_S} s")
        if exp.state != "done":
            raise RuntimeError(exp.note)
    elif word == "export-more":                # export-more [<target> [<format>]]: "+ Another version", with its target / file type
        e = mix.export
        e.addVersion()
        n = len(e._more.rows) - 1
        for key, v in zip(("target", "format"), rest):
            e.setVersion(n, key, v)
    elif word == "export-what":                # export-what <all|range|section:<id>>: the sheet's What
        mix.export.setRange(rest[0])
        if mix.export.range != rest[0]:
            raise RuntimeError(f"export-what: no range {rest[0]!r} (there are: {', '.join(r['value'] for r in mix.export.ranges)})")
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


MIX_WORDS = ("deliver", "export-as", "export-more", "export-what", "export", "clean-take", "model-panel", "model-download", "duck-add", "duck-open", "duck-set")


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


def shot(bridge, win, path):
    """The window as a picture once the newest sound has rendered and the 160 ms reveals have finished."""
    wait_render(bridge)
    end = time.monotonic() + 0.6
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.02)
    img = win.grabWindow()
    if img.isNull() or not img.save(path):
        raise RuntimeError(f"shot: could not save {path}")


def do_step(bridge, win, step, recorder=None):
    bridge.__dict__["_refused"] = ""             # an action refused during this step fails it (action_slots._refuse)
    _do_step(bridge, win, step, recorder)
    if bridge.__dict__.get("_refused"):
        raise RuntimeError(f"step {step!r}: refused: {bridge.__dict__['_refused']}")


def _do_step(bridge, win, step, recorder=None):
    word, *rest = step.split()
    if word == "dock":
        bridge.workspace.setDock(rest[0])
    elif word == "page":                      # the pages are gone: an old script's page opens the dock that took its place
        if rest[0] not in OLD_PAGES:
            raise ValueError(f"step {step!r}: no such page (timeline, mix or instruments)")
        bridge.workspace.setDock(OLD_PAGES[rest[0]])
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
    elif word == "song-open":                 # nothing selected: the song in the settings panel
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
    elif word in SELECT_WORDS:               # selection and its actions (steps_select.py)
        do_select_step(bridge, win, word, rest)
    elif word in SWAP_WORDS:                 # swap stepping and the export presets (steps_swap.py)
        do_swap_step(bridge, word, rest)
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
    elif word == "select-last":               # select-last <n>: the last n notes / hits / clips made on the Editor's track
        t = bridge.doc.item(bridge._track)
        made = [i["id"] for k in ("notes", "hits", "clips", "sounds", "lines") for i in t.get(k, [])][-int(rest[0]):]
        bridge.pickMany(made)
    elif word == "handle-first":              # handle-first <part> <dt s>: a handle drag on the first selected item
        do_select_step(bridge, win, "handle", [bridge.selectedIds[0], *rest])
    elif word == "agent":                     # agent <label>|<json calls>: an agent's change (another author), for the walks
        from rostrum_core import Who
        label, _, calls = " ".join(rest).partition("|")
        bridge.doc.apply(json.loads(calls), Who.agent("Claude"), label=label)
    elif word == "shot":                      # shot <file.png>: a picture of the window now (the flow walks: one per step)
        shot(bridge, win, " ".join(rest))
    elif word == "wait":                      # let background work (the listen pictures) land: wait <seconds>
        end = time.monotonic() + float(rest[0])
        while time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.02)
    else:
        raise ValueError(f"unknown step {step!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
