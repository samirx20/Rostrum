"""Scripted steps for screenshots and checks. Each goes through the same bridge call a click or drag makes.

    select <id> | page design|draw|animate | time <s> | set <param> <json value> | scrub <param> <v> <v> …
    animate <param> (the key mark's toggle) | drag <layer> <dx> <dy> (canvas drag, composition px; in an auto layout it
    changes the layer's slot: the same drag slots, so <dx> <dy> moves the pointer)
    curves on|off | curvedrag <key> <dt> <dv> | handledrag <key> <1|2> <dx> <dy> (the curve editor)
    keydrag <key id> <t> | open <layer> (timeline rows) | fold <layer> (layers panel) | pick <x> <y>
    undo | redo | more | commands [query …] | run <command key> | play
    marker add <s> | marker move <name> <s> | marker rename <name> <new name> | marker remove <name> (ruler flags; _ for spaces)
  Draw page (on the selected drawing layer): draw <x> <y> <x> <y> … (one stroke, composition px)
    brush <setting> <value> | newframe [copy] | hold <+n|-n> | frame next|prev | onion on|off
  Design page, paths: pen <x,y> <x,y,hx,hy> … [close] (one new path: a point, or a press at x,y dragged to hx,hy =
    a smooth point; composition px) | pointpick <layer> <i> (select a point: its handles show) | pointdrag <layer> <i> <dx> <dy> [in|out] (a point, or its handle)
  Handles: resize <layer> <nw|n|ne|e|se|s|sw|w> <dx> <dy> [shift] [alt] | rotate <layer> <deg> [shift] (turn by that many
    degrees) | boxselect <x0> <y0> <x1> <y1> (the rubber band) | shiftpick <layer> (add / remove) | movesel <dx> <dy> (move all selected)
  Add and import: add <type> (the Add menu's entry; image / video: add image <path>) | addmenu open|close |
    import <path> [page=<n>] [text=outline] [keep=on] (the Import panel's job, waits, fails like it) | importstart <path> … (starts it,
    doesn't wait) | importpanel open [path]|close
    problems open|close (the Problems panel, after the list is worked out) | inspectorscroll <px>
  Export: export <mp4|prores4444|webm|gif|png|exr|lottie> [alpha=on|off] [depth=8|16] [start=<s>] [end=<s>] (the Export button's
    job; waits for it) | exportpanel open [format]|close | exportcancel [format] (start one, then Cancel it)
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import json
import time

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject


def value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text            # a bare word is a string: set align left


def steps_export(bridge, step, rest):
    job = bridge.exporter
    job.setFormat(rest[0])
    for kv in rest[1:]:
        key, _, v = kv.partition("=")
        if key not in ("alpha", "depth", "start", "end"):
            raise ValueError(f"step {step!r}: unknown setting {key!r}")
        job.setSetting(key, v in ("on", "true", "1") if key == "alpha" else float(v))
    job.start()
    if job.state == "running" and not job.wait(600):
        raise RuntimeError(f"step {step!r}: the export did not finish in 10 minutes")
    if job.state != "done":
        raise RuntimeError(f"step {step!r}: {job.note}")
    print(f"export {job.format}: {job.path} {job.facts}")


def steps_import(bridge, step, rest):
    job = bridge.importer
    job.setFile(rest[0])
    for kv in rest[1:]:
        key, _, v = kv.partition("=")
        if key == "page":
            job.setPage(int(v))
        elif key == "text":
            job.setText(v)
        elif key == "keep":
            job.setKeepSize(v in ("on", "true", "1"))
        else:
            raise ValueError(f"step {step!r}: unknown setting {key!r}")
    job.run()
    if step.startswith("importstart"):               # leave it running (for a picture of the progress)
        return
    if job.state == "running" and not job.wait(600):
        raise RuntimeError(f"step {step!r}: the import did not finish in 10 minutes")
    if job.state != "done":
        raise RuntimeError(f"step {step!r}: {job.note}")
    print(f"import: {job.note}; not carried over: {job.report}")


def steps_cancel(bridge, step, rest):
    """Start an export and press Cancel once its engine runs: the panel must end on "cancelled"."""
    job = bridge.exporter
    job.setFormat(rest[0] if rest else "png")
    job.start()
    t0 = time.time()
    while job.job.engine is None and job.running() and time.time() - t0 < 20:
        QCoreApplication.processEvents()
    time.sleep(0.4)
    job.cancel()
    job.wait(60)
    if job.state != "cancelled":
        raise RuntimeError(f"step {step!r}: expected the export to be cancelled, it is {job.state!r}: {job.note}")


def do_step(bridge, win, step):
    word, *rest = step.split()
    if word == "select":
        bridge.select(rest[0])
    elif word == "exportcancel":
        steps_cancel(bridge, step, rest)
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
    elif word in ("resize", "rotate", "boxselect", "shiftpick", "movesel"):
        from .handle_steps import steps_handles
        steps_handles(bridge, step, rest)
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
    elif word == "draw":
        xy = [float(v) for v in rest]
        if len(xy) < 2 or len(xy) % 2 or not bridge.painter.beginStroke(xy[0], xy[1], 1.0):
            raise RuntimeError(f"step {step!r}: needs x y pairs and a selected drawing layer")
        for x, y in zip(xy[2::2], xy[3::2]):
            bridge.painter.strokeTo(x, y, 1.0)
        bridge.painter.endStroke()
    elif word in ("curves", "curvedrag", "handledrag"):
        from .curves import steps_curves
        steps_curves(bridge, step, rest)
    elif word == "pen":
        from .pen import steps_pen
        steps_pen(bridge, step, rest)
    elif word == "pointpick":
        from .pen import steps_pointpick
        steps_pointpick(bridge, step, rest)
    elif word == "pointdrag":
        from .pen import steps_pointdrag
        steps_pointdrag(bridge, step, rest)
    elif word == "brush":
        bridge.painter.setValue(rest[0], value(" ".join(rest[1:])))
    elif word == "newframe":
        bridge.painter.newFrame(rest[:1] == ["copy"])
    elif word == "clear":
        bridge.painter.clearDrawing()
    elif word == "hold":
        bridge.painter.holdBy(int(rest[0]))
    elif word == "frame":
        bridge.painter.goFrame(1 if rest[0] == "next" else -1)
    elif word == "onion":
        bridge.painter.setOnion(rest[0] == "on")
    elif word == "marker":                       # the ruler's flag edits, through the same MarkerWatch slots
        from rostrum_core.markers import find
        m = bridge.marks
        ref = rest[1].replace("_", " ") if len(rest) > 1 else ""            # a marker's name, _ for spaces
        mid = find(m.rows(), ref)["id"] if rest[0] != "add" else ""
        if rest[0] == "add":
            bridge.setTime(float(rest[1]))
            m.add(bridge.time)
        elif rest[0] == "move":
            m.move(mid, float(rest[2]))
        elif rest[0] == "rename":
            m.rename(mid, " ".join(rest[2:]))
        elif rest[0] == "remove":
            m.remove(mid)
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
    elif word == "export":
        steps_export(bridge, step, rest)
    elif word == "add":
        if rest[0] in ("image", "video") and rest[1:]:
            bridge.adder.addFile(rest[0], rest[1])
        else:
            bridge.adder.add(rest[0])
    elif word == "addmenu":
        QMetaObject.invokeMethod(win, "setAddOpen", Q_ARG("QVariant", rest[0] == "open"))
    elif word in ("import", "importstart"):
        steps_import(bridge, step, rest)
    elif word == "importpanel":
        if rest[1:]:
            bridge.importer.setFile(rest[1])
        QMetaObject.invokeMethod(win, "setImportOpen", Q_ARG("QVariant", rest[0] == "open"))
    elif word == "problems":                     # the Problems panel, once the list is worked out
        if not bridge.problems.wait(30):
            raise RuntimeError(f"step {step!r}: the problems list was not ready in 30 s")
        QMetaObject.invokeMethod(win, "setProblemsOpen", Q_ARG("QVariant", rest[0] == "open"))
    elif word == "inspectorscroll":              # scroll the (visible) inspector to <px> from its top
        from PySide6.QtCore import QObject
        end = time.time() + 0.4                  # rows that just appeared ease in (Theme.reveal): let them finish
        while time.time() < end:
            QCoreApplication.processEvents()
        for f in win.findChildren(QObject, "inspectorScroll"):
            if f.property("visible"):
                f.setProperty("contentY", min(float(rest[0]), max(0.0, f.property("contentHeight") - f.property("height"))))
    elif word == "exportpanel":
        if rest[1:]:
            bridge.exporter.setFormat(rest[1])
        QMetaObject.invokeMethod(win, "setExportOpen", Q_ARG("QVariant", rest[0] == "open"))
    else:
        raise ValueError(f"unknown step {step!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
