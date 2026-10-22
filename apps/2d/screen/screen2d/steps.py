"""Scripted steps for screenshots and checks. Each goes through the same bridge call a click or drag makes.

    select <id> | tool move|pen|draw | time <s> | set <param> <json value> | scrub <param> <v> <v> …
    animate <param> (the key mark's toggle) | drag <layer> <dx> <dy> (canvas drag, composition px; in an auto layout it
    changes the layer's slot: the same drag slots, so <dx> <dy> moves the pointer)
    curves on|off | curvedrag <key> <dt> <dv> | handledrag <key> <1|2> <dx> <dy> (the curve editor)
    keydrag <key id> <t> | bardrag <layer> <move|start|end> <from s> <to s> (a layer bar on the timeline: pointer pressed at
    <from>, let go at <to>; <to> may be #marker_name, _ for spaces: the dragged edge lands on it and the layer is tied) | open <layer> (timeline rows) | fold <layer> (layers panel) | pick <x> <y>
    front | back | forward | backward | delete (the selected layer(s): Ctrl+Shift+] / Ctrl+Shift+[ / Ctrl+] / Ctrl+[ / Delete) |
    rename <layer> <name> | undo | redo | more | commands [query …] | run <command key> | play | play <seconds> [blur] [full|half|quarter]
    (plays, with full motion blur or not, at that Preview size, then prints the frames shown per second and each stage's time: screen2d/playstats.py)
    marker add <s> | marker move <name> <s> | marker rename <name> <new name> | marker remove <name> (ruler flags; _ for spaces)
  timeline compact|full (this tool's timeline height) | Draw tool (tool draw; paints on the selected drawing layer, or makes one): draw <x> <y> <x> <y> … (one stroke, composition px)
    brush <setting> <value> | newframe [copy] | hold <+n|-n> | frame next|prev | onion on|off
  Paths (tool pen): pen <x,y> <x,y,hx,hy> … [close] (one new path: a point, or a press at x,y dragged to hx,hy =
    a smooth point; composition px) | pointpick <layer> <i> (select a point: its handles show) | pointdrag <layer> <i> <dx> <dy> [in|out] (a point, or its handle)
  Handles: resize <layer> <nw|n|ne|e|se|s|sw|w> <dx> <dy> [shift] [alt] | rotate <layer> <deg> [shift] (turn by that many
    degrees) | boxselect <x0> <y0> <x1> <y1> (the rubber band) | shiftpick <layer> (add / remove) | movesel <dx> <dy> (move all selected)
  Add and import: add <type> (the Add menu's entry; image / video: add image <path>) | addmenu open|close |
    import <path> [page=<n>] [text=outline] [keep=on] (the Import panel's job, waits, fails like it) | importstart <path> … (starts it,
    doesn't wait) | importpanel open [path]|close
    problems open|close (the Problems panel, after the list is worked out) | inspectorscroll <px>
  Select, then act: selectmany <id> <id> … (those layers, the first is the primary) | act <action> (an entry of the one
    list on the selection: group, ungroup, mask, union, align_left, distribute_x, match_w, lock, hide, delete, front …;
    fails when the selection doesn't allow it) | nudge <dx> <dy> (the arrow keys, px) | actionmenu | actionbar (print what they offer)
  Inspector kit: find <text> (the search box; alone clears it) | group <name> (fold / open a group) | reveal <field> (bring a field into view)
  Export: export <mp4|prores4444|webm|gif|png|exr|lottie> [alpha=on|off] [depth=8|16] [start=<s>] [end=<s>] (the Export button's
    job; waits for it) | exportpanel open [format]|close | exportcancel [format] (start one, then Cancel it) |
    exportto <path> [replace|both|cancel] | exportshow (export_steps.py)
  Files (file_steps.py): new [name] | save | saveas <name> | openproject <path> | autosave | restore | discard |
    filemenu open|close | askclose
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import json
import time

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject

from .export_steps import WORDS as EXPORT_WORDS, do_export_step
from .file_steps import WORDS as FILE_WORDS, do_file_step


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


def steps_play(bridge, seconds, blur, size="full"):
    """Play for `seconds` (after the Problems list's first look, which shares the CPU) at Preview size `size`, then
    print the frames shown."""
    from .playstats import STATS
    bridge.problems.wait(60)
    bridge.playback.setBlur(blur)
    bridge.playback.setSize(size)
    STATS.on = True
    STATS.reset()
    bridge.togglePlay()
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        QCoreApplication.processEvents()
    bridge.togglePlay()
    print(f"play {seconds:g} s from the playhead: {STATS.report()}")
    STATS.on = STATS.log


def steps_bardrag(bridge, step, rest):
    """bardrag <layer> <move|start|end> <from s> <to s>: the timeline's bar drag through its own slots. A `#marker` target
    puts the dragged edge on that marker (the pointer goes as far as the edge needs) and lets go with snapping on."""
    layer, part, t0 = rest[0], rest[1], float(rest[2])
    if not bridge.beginBarDrag(layer, part, t0):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
    snap, to = 0.0, rest[3]
    if to.startswith("#"):
        name, times = to[1:], bridge.times()
        name = name if name in times else name.replace("_", " ")
        item = bridge.placed_item(layer)
        edge = (item["end"] if item.get("end", 36000.0) < 36000.0 else bridge.comp()["duration"]) if part == "end" else item.get("start", 0.0)
        snap, to = 0.1, t0 + times[name] - edge
    for f in (0.25, 0.5, 0.75, 1.0):
        bridge.barDragTo(t0 + (float(to) - t0) * f, snap)
    bridge.endDrag()


def do_step(bridge, win, step):
    word, *rest = step.split()
    if word == "select":
        bridge.select(rest[0])
    elif word == "exportcancel":
        steps_cancel(bridge, step, rest)
    elif word == "tool":
        bridge.setTool(rest[0])
    elif word == "timeline":                     # timeline compact|full: the button at the timeline header's right end
        QMetaObject.invokeMethod(win, "setTimeline", Q_ARG("QVariant", rest[0] == "compact"), Q_ARG("QVariant", None))
    elif word == "find":
        bridge.setSearch(" ".join(rest))
    elif word == "group":
        bridge.toggleGroup(" ".join(rest))
    elif word == "reveal":
        bridge.revealField(rest[0])
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
    elif word == "bardrag":
        steps_bardrag(bridge, step, rest)
    elif word == "open":
        bridge.toggleFold(rest[0])
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
        ref = rest[1] if len(rest) > 1 else ""                              # a marker's name, _ for spaces
        names = [r["name"] for r in m.rows()]
        ref = ref if ref in names else ref.replace("_", " ")
        mid = find(m.rows(), ref)["id"] if rest[0] != "add" else ""
        if rest[0] == "add":
            bridge.setTime(float(rest[1]))
            m.add(bridge.time)
        elif rest[0] == "move":
            m.move(mid, float(rest[2]))
        elif rest[0] == "rename":
            m.rename(mid, " ".join(rest[2:]).replace("_", " "))
        elif rest[0] == "remove":
            m.remove(mid)
    elif word in ("undo", "redo"):
        getattr(bridge, word)()
    elif word == "more":
        bridge.toggleMore()
    elif word == "play" and rest:                # play for <seconds>, then print the frames shown per second
        steps_play(bridge, float(rest[0]), "blur" in rest[1:], next((w for w in rest[1:] if w != "blur"), "full"))
    elif word == "play":
        bridge.togglePlay()
    elif word == "commands":
        QMetaObject.invokeMethod(win, "openCommands", Q_ARG("QVariant", " ".join(rest)))
    elif word == "run":
        bridge.run(rest[0])
    elif word == "layerdrag":                    # layerdrag <layer> <above|below|into> <target layer> (the Layers panel's drop)
        if not bridge.moveLayer(rest[0], rest[2], rest[1]):
            raise RuntimeError(f"step {step!r}: nothing moved")
    elif word == "layerdrop":                    # layerdrop <layer> <above|below|into> <target>: show the drop line, no move
        from PySide6.QtCore import QObject
        box = win.findChild(QObject, "layersList")
        for name, v in (("dragId", rest[0]), ("dropWhere", rest[1]), ("dropRow", rest[2])):
            box.setProperty(name, v)
    elif word == "mousedrag":                    # mousedrag <x0> <y0> <x1> <y1> [right]: a real press, pull and release in the window
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        x0, y0, x1, y1 = (int(v) for v in rest[:4])
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, QPoint(x0, y0))
        for k in range(1, 9):
            QTest.mouseMove(win, QPoint(x0 + (x1 - x0) * k // 8, y0 + (y1 - y0) * k // 8))
            QCoreApplication.processEvents()
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, QPoint(x1, y1))
    elif word == "layermenu":                    # layermenu <layer> [open|<command>]: the row's right-click menu
        QMetaObject.invokeMethod(win, "openLayerMenu", Q_ARG("QVariant", rest[0]))
        if rest[1:] and rest[1] != "open":
            bridge.run(f"layer:{rest[1]}")
    elif word == "selectmany":
        bridge._select(rest)
    elif word == "act":
        if not bridge.layerCommand(rest[0]):
            raise RuntimeError(f"step {step!r}: {bridge.status or 'not available for the selection'}")   # the why
    elif word == "nudge":
        bridge.nudge(float(rest[0]), float(rest[1]))
    elif word == "actionmenu":                   # print the right-click menu's entries
        print(word, [e["value"] for e in bridge.actionMenu()])
    elif word == "actionbar":                    # print the context bar's buttons
        print(word, [e["label"] for e in bridge.actions.bar["items"]])
    elif word == "canvasmenu":                   # the canvas's right-click menu, opened on the selection
        QMetaObject.invokeMethod(win, "openCanvasMenu")
    elif word in ("front", "back", "forward", "backward", "delete", "duplicate"):    # the layer-order shortcuts (layer_order.py)
        if not bridge.layerCommand(word):
            raise RuntimeError(f"step {step!r}: not available for the selection")
    elif word == "rename":                       # rename <layer> <new name> (the Layers panel's name box)
        if not bridge.renameLayer(rest[0], " ".join(rest[1:])):
            raise RuntimeError(f"step {step!r}: nothing renamed")
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
    elif word in EXPORT_WORDS:
        do_export_step(bridge, word, rest, step)
    elif word in FILE_WORDS:
        do_file_step(bridge, win, word, rest, step)
    else:
        raise ValueError(f"unknown step {step!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
