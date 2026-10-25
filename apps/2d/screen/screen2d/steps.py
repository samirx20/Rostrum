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
    brush <setting> <value> | newframe [copy] | hold <+n|-n> | frame next|prev | onion on|off | paintlayer | painton selected|new|own|fill
  Paths (tool pen): pen <x,y> <x,y,hx,hy> … [close] (one new path: a point, or a press at x,y dragged to hx,hy =
    a smooth point; composition px) | pointpick <layer> <i> (select a point: its handles show) | pointdrag <layer> <i> <dx> <dy> [in|out] (a point, or its handle)
  Handles: resize <layer> <nw|n|ne|e|se|s|sw|w> <dx> <dy> [shift] [alt] | rotate <layer> <deg> [shift] (turn by that many
    degrees) | boxselect <x0> <y0> <x1> <y1> [shift] [ctrl] (the rubber band) | shiftpick <layer> (add / remove) | movesel <dx> <dy> (move all selected) | groupresize <nw|n|ne|e|se|s|sw|w> <dx> <dy> [shift] [alt] / grouprotate <deg> [shift] (the box round several selected layers)
  Add and import: add <type> (the Add menu's entry; image / video: add image <path>) | flyout <group>|close (a rail group's flyout) |
    import <path> [page=<n>] [text=outline] [keep=on] (the Import panel's job, waits, fails like it) | importstart <path> … (starts it,
    doesn't wait) | importpanel open [path]|close | drop <path> [x y] | library open|close (the Library drawer) |
    brand <colors|textStyles|logos> <name, _ for spaces> <#rrggbb | text style id | file> (into the project's brand kit)
    (a file let go on the canvas) | pastetext <text> (the clipboard holds it, then Ctrl+V: a Figma link opens Import)
    problems open|close (the kit's Problems chip list, after the list is worked out: layout_run.kit_step) | inspectorscroll <px>
  Select, then act: selectmany <id> <id> … (those layers, the first is the primary) | act <job> (an action that has a key:
    group, ungroup, mask, union, align_left, lock, hide, delete, front …) | do <action id> (any action of the list, as a menu click:
    distribute_x, match_w, effect_grain …); both fail, saying why, when the selection doesn't allow it | nudge <dx> <dy> (the arrow keys, px) | actionmenu | actionbar (print what they offer)
  Inspector kit: find <text> (the search box; alone clears it) | group <name> (fold / open a group) | reveal <field> (bring a field into view)
  Export (the kit's Export sheet): export <mp4|prores4444|webm|gif|png|exr|lottie> [alpha=on|off] [depth=8|16]
    [quality=<q>] [range=<a→b>] (the sheet's Export; waits for it) | exportpanel open [format]|close (= exportsheet) |
    exportcancel [format] (start one, then Cancel it) | exportto <folder> [replace|both|cancel] | exportshow | exportsize | exportarea frame|items|world (export_steps.py);
    the kit's own: exportsheet, exportwhere, exportnow, job-show, job-failed (rostrum_gui/export_steps.py)
  Files (file_steps.py): new [name] | openproject <path> | startscreen open|close | version [name] | duplicateproject <name> |
    filemenu open|close | scenemenu open|new|<scene id> (the › Scene ▾ crumb)
  Keys (key_steps.py): keypick | keybox | keydrag2 | keystretch | keydelete | showanim | ease | easekey | easecurve |
    spring | keytime | keyvalue | easemenu | keyhere (K) | keycopy | keypaste | stagger <f> [order] [open] | event prev|next
  Creation tools (create_steps.py): shape <rect|ellipse> x0 y0 x1 y1 [shift] [alt] | text <x> <y> <words> | textbox x0 y0 x1 y1 <words> | edittext <layer> <words>
  Paint (paint_steps.py): preset <id> | painttool <tool> | brushedit on|off | keytap <key> [mods] | fill <x> <y> | fillmode on|off | gap <size> | paintpick|paintremove <paint> | paintset <paint> <field> <v> |
    paintmove <paint> <row> | painttoggle <field> on|off
  Paintings (painting_steps.py): paintingop <op> <target|-> [<json>] | paintingsay
    | paintingopen <id> | paintingclose | paintinguse <layer> | opentime <id> [n] [profile] (open_steps.py: a painting opened on its own)
  Strokes (stroke_steps.py): altpick <x> <y> [click] | altoff | lasso <x,y> … [open] | selectstrokes on|off | strokesmove <dx> <dy> |
    strokesturn <deg> [scale] | strokesdelete | strokescopy | strokespaste | strokesclear | clickarea canvas|timeline|settings
  Sound (soundtrack_steps.py): sound wait | mute on|off | beats on|off | beat prev|next | scrub <s> | play <s> |
    wav <path> | pick <item|-> | menu | open [dry] | problem <png>
  Hover preview (H63): hoverobj <objectName> [ms] (click_steps.py: rest on a control) | canvasreport (the canvas's fingerprint + history length)
  Frame (frame_steps.py): frame pick | frame drag <dx> <dy> | frame corner <dx> | frame turn <deg> | frametime drag|zoom|turn [n]
  Drag cost (drag_steps.py): dragtime bar|trim|key|layer|frame|scrub [n] [profile]
  Edit cost (edit_steps.py): edittime field|dragend|key|pin|undo [n] [layer=<id>] [profile]
  Stroke cost (stroke_time.py): painttime <layer> <x0> <y0> <x1> <y1> [n] | painthold <x> <y> <x> <y> … (the pen left down)
  Selection cost (rostrum_gui/select_steps.py, any app): selecttime <id> <id> … [n]
  View (view_steps.py): zoom <percent|fit> [x y] | pan <dx> <dy> | fitsel | viewmenu | lookthrough on|off | draghold <layer> <dx> <dy> [ctrl] [shift]
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import json
import time

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject

from .create_steps import WORDS as CREATE_WORDS, do_create_step
from .click_steps import WORDS as CLICK_WORDS, do_click_step
from .export_steps import WORDS as EXPORT_WORDS, do_export_step
from .key_steps import WORDS as KEY_WORDS, do_key_step
from .file_steps import WORDS as FILE_WORDS, do_file_step
from .paint_steps import WORDS as PAINT_WORDS, do_paint_step
from .painting_steps import WORDS as PAINTING_WORDS, do_painting_step
from .open_steps import WORDS as OPEN_WORDS, do_open_step
from .stroke_steps import WORDS as STROKE_WORDS, do_stroke_step
from .view_steps import WORDS as VIEW_WORDS, do_view_step
from .frame_steps import WORDS as FRAME_WORDS, do_frame_step
from .soundtrack_steps import WORDS as SOUND_WORDS, do_sound_step
from .rig_steps import WORDS as RIG_WORDS, do_rig_step
from .drag_steps import WORDS as DRAG_WORDS, do_drag_step
from .edit_steps import WORDS as EDIT_WORDS, do_edit_step
from .stroke_time import WORDS as STROKE_TIME_WORDS, do_stroke_time


def value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text            # a bare word is a string: set align left


def steps_export(bridge, step, rest):
    job = bridge.exporter
    job.setFormat(rest[0])
    if job.format != rest[0]:
        raise ValueError(f"step {step!r}: no format {rest[0]!r}")
    for kv in rest[1:]:
        key, _, v = kv.partition("=")
        if key == "range":
            job.setRange(v.replace("_", " "))
            if job.range != v.replace("_", " "):
                raise ValueError(f"step {step!r}: no range {v!r} in {[r['value'] for r in job.ranges_list()]}")
        elif key in ("alpha", "depth", "quality", "size", "rate"):
            job.setSetting(key, v in ("on", "true", "1") if key == "alpha" else v)
        else:
            raise ValueError(f"step {step!r}: unknown setting {key!r}")
    job.request()
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
    job._engine = None
    job.request()
    t0 = time.time()
    while job._engine is None and job.running() and time.time() - t0 < 20:
        QCoreApplication.processEvents()
    time.sleep(0.4)
    job.cancel()
    job.wait(60)
    if job.state != "cancelled":
        raise RuntimeError(f"step {step!r}: expected the export to be cancelled, it is {job.state!r}: {job.note}")


def steps_play(bridge, seconds, blur, size="full"):
    """Play for `seconds` (after the Problems list's first look, which shares the CPU) at Preview size `size`, then
    print the frames shown and the screen thread's busy time per frame shown (its event loop runs as a person's does)."""
    from .drag_steps import Busy, _wait
    from .playstats import STATS
    bridge.problems.wait(60)
    bridge.playback.setBlur(blur)
    bridge.playback.setSize(size)
    STATS.on = True
    STATS.reset()
    busy = Busy()
    bridge.togglePlay()
    _wait(seconds * 1000)
    bridge.togglePlay()
    busy.close()
    print(f"play {seconds:g} s from the playhead: {STATS.report()};  screen thread {busy.now() / max(STATS.shown, 1):.1f} ms per frame shown")
    STATS.on = STATS.log


def steps_bardrag(bridge, step, rest):
    """bardrag <layer> <move|start|end> <from s> <to s> [snap] [hold]: the timeline's bar drag through its own slots. A `#marker` target
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
    snap = snap or (0.1 if "snap" in rest[4:] else 0.0)      # `snap`: within 0.1 s (time_snap.py)
    for f in (0.25, 0.5, 0.75, 1.0):
        bridge.barDragTo(t0 + (float(to) - t0) * f, snap)
    print("drag label", ascii(bridge.timeSnap.text))
    if "hold" not in rest[4:]:                   # `hold`: not let go yet (a picture mid-drag)
        bridge.endDrag()


def steps_bartime(bridge, step, rest):
    """bartime <layer> <move|start|end> <from s> <to s> <n>: n moves of a bar drag, each one's GUI-thread time (the
    drag's slot, the document, the rows, the bindings: processed until the screen is idle), then the release's."""
    import statistics
    import time
    from PySide6.QtCore import QCoreApplication
    layer, part, t0, t1, n = rest[0], rest[1], float(rest[2]), float(rest[3]), int(rest[4])
    if not bridge.beginBarDrag(layer, part, t0):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
    ms = []
    for i in range(1, n + 1):
        t = time.perf_counter()
        bridge.barDragTo(t0 + (t1 - t0) * i / n, 0.1)
        QCoreApplication.processEvents()
        ms.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    bridge.endDrag()
    QCoreApplication.processEvents()
    q = sorted(ms)
    print(f"bartime {layer} {part}: {n} moves; GUI thread median {statistics.median(q):.1f}, p95 {q[max(0, int(n * 0.95) - 1)]:.1f}, "
          f"max {q[-1]:.1f} ms; release {(time.perf_counter() - t) * 1000:.1f} ms")


def do_step(bridge, win, step):
    word, *rest = step.split()
    if word == "select":
        bridge.select(rest[0])
    elif word == "exportcancel":
        steps_cancel(bridge, step, rest)
    elif word == "tool":
        bridge.setTool(rest[0])
    elif word == "timeline":                     # timeline compact|full: the button at the ruler's right end
        win.setProperty("timelineFolded", rest[0] == "compact")
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
    elif word in ("resize", "rotate", "boxselect", "shiftpick", "movesel", "groupresize", "grouprotate"):
        from .handle_steps import steps_handles
        steps_handles(bridge, step, rest)
    elif word == "keydrag":
        bridge.beginKeyDrag(rest[0])
        bridge.keyDragTo(float(rest[1]))
        bridge.endDrag()
    elif word == "bardrag":
        steps_bardrag(bridge, step, rest)
    elif word == "bartime":
        steps_bartime(bridge, step, rest)
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
    elif word == "onion":
        bridge.painter.setOnion(rest[0] == "on")
    elif word == "paintlayer":                   # "Paint layers +": a new paint layer on top, highlighted
        bridge._paint_layers.add()
    elif word == "painton":                      # painton selected|new|own|fill: Painting on › Layer ▾
        bridge.painter.paintOn(rest[0])
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
    elif word == "mousedrag":                    # mousedrag <x0> <y0> <x1> <y1> [right] [alt] [hold]: a real press, pull and release in the window
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        x0, y0, x1, y1 = (int(v) for v in rest[:4])
        mod = Qt.AltModifier if "alt" in rest[4:] else Qt.NoModifier           # mousedrag … alt: pressed with Alt held (a frame corner zooms about the opposite corner)
        button = Qt.RightButton if "right" in rest[4:] else Qt.LeftButton      # … right: Alt + right-drag sizes the brush
        if "altkey" in rest[4:]:                 # … altkey: the Alt key held down first, as a person does
            QTest.keyPress(win, Qt.Key_Alt)
            mod = Qt.AltModifier
        QTest.mousePress(win, button, mod, QPoint(x0, y0))
        for k in range(1, 9):
            if k == 5 and "altmid" in rest[4:]:  # mousedrag … altmid: Alt goes down halfway through the drag
                QTest.keyPress(win, Qt.Key_Alt)
                mod = Qt.AltModifier
            QTest.mouseMove(win, QPoint(x0 + (x1 - x0) * k // 8, y0 + (y1 - y0) * k // 8))
            QCoreApplication.processEvents()
        if "hold" in rest[4:]:                   # … hold: not let go (a picture mid-drag)
            return
        QTest.mouseRelease(win, button, mod, QPoint(x1, y1))
        if "altmid" in rest[4:] or "altkey" in rest[4:]:
            QTest.keyRelease(win, Qt.Key_Alt)
    elif word == "mousemove":                    # mousemove <x> <y>: the pointer moves there in the window (hover)
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest
        QTest.mouseMove(win, QPoint(int(rest[0]), int(rest[1])))
        QTest.qWait(150)
    elif word == "mouseclick":                   # mouseclick <x> <y> [right] [ctrl|shift]: a real click in the window
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        button = Qt.RightButton if "right" in rest[2:] else Qt.LeftButton
        mods = Qt.ControlModifier if "ctrl" in rest[2:] else Qt.ShiftModifier if "shift" in rest[2:] else Qt.NoModifier
        QTest.mouseClick(win, button, mods, QPoint(int(rest[0]), int(rest[1])))
    elif word == "layermenu":                    # layermenu <layer> [open|<command>]: the row's right-click menu
        QMetaObject.invokeMethod(win, "openLayerMenu", Q_ARG("QVariant", rest[0]))
        if rest[1:] and rest[1] != "open":
            bridge.run(f"layer:{rest[1]}")
    elif word == "selectmany":
        bridge._select(rest)
    elif word == "act":
        if not bridge.layerCommand(rest[0]):
            raise RuntimeError(f"step {step!r}: {bridge.status or 'not available for the selection'}")   # the why
    elif word == "do":                           # do <action id>: any action of the list as a menu click runs it (effect_grain …)
        key = rest[0] if ":" in rest[0] else f"layer:{rest[0]}"     # the list's ids are "layer:<id>" (actions._action)
        if not bridge.run(key):                  # the bridge's run, as a menu click (action_slots.run; the hub's returns nothing)
            raise RuntimeError(f"step {step!r}: {bridge.status or 'not available for the selection'}")
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
    elif word == "flyout":                       # flyout <group> (shapes, media, view) | flyout close: a rail group's flyout
        QMetaObject.invokeMethod(win, "openFlyout", Q_ARG("QVariant", "" if rest[0] == "close" else rest[0]))
    elif word in ("import", "importstart"):
        steps_import(bridge, step, rest)
    elif word == "drop":                         # drop <path> [<x> <y>]: a file let go on the canvas (comp px)
        job = bridge.importer
        x, y = (float(rest[1]), float(rest[2])) if rest[2:] else (float("nan"), float("nan"))
        if not job.dropFiles([rest[0]], x, y):
            raise RuntimeError(f"step {step!r}: the drop was refused")
        while (job.running() or job._queue) and job.wait(600):
            pass
        if job.state != "done":
            raise RuntimeError(f"step {step!r}: {job.note}")
        print(f"drop: {job.note}")
    elif word == "pastetext":                    # pastetext <text>: the clipboard holds this text, then Ctrl+V
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(" ".join(rest))
        bridge.pasteLayers()
        QCoreApplication.processEvents()
    elif word == "library":
        bridge.library.setOpen(rest[0] == "open")
    elif word == "brand":                        # brand <section> <name> <value>: the MCP tool's add (brand_kit.py)
        from rostrum2d import brand_kit, text_styles
        name, given = rest[1].replace("_", " "), rest[2]     # not `value`: that is this module's reader (the set step)
        entry = ({"value": given} if rest[0] == "colors" else {"file": given} if rest[0] == "logos"
                 else text_styles.values(bridge.doc.item(given)))
        brand_kit.add(bridge.doc.folder, rest[0], {"name": name, **entry})
        bridge.library.setOpen(bridge.library.open)          # read again
    elif word == "importpanel":
        if rest[1:]:
            bridge.importer.setFile(rest[1])
        QMetaObject.invokeMethod(win, "setImportOpen", Q_ARG("QVariant", rest[0] == "open"))
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
    elif word in KEY_WORDS:
        do_key_step(bridge, word, rest, step)
    elif word in EXPORT_WORDS:
        do_export_step(bridge, word, rest, step)
    elif word in FILE_WORDS:
        do_file_step(bridge, win, word, rest, step)
    elif word in VIEW_WORDS:                     # zoom, pan, fitsel, draghold (view_steps.py)
        do_view_step(bridge, win, word, rest, step)
    elif word in FRAME_WORDS:                    # frame pick | drag | corner | turn, frametime (frame_steps.py)
        do_frame_step(bridge, word, rest, step)
    elif word in CREATE_WORDS:
        do_create_step(bridge, word, rest, step)
    elif word in PAINT_WORDS:                    # Fill, the paint layers panel (paint_steps.py)
        do_paint_step(bridge, word, rest, step, win)
    elif word in OPEN_WORDS:                     # paintingopen <id>, paintingclose, paintinguse <layer> (open_steps.py)
        do_open_step(bridge, word, rest, step)
    elif word in PAINTING_WORDS:                 # paintingop <op> <target> <json>, paintingsay (painting_steps.py)
        do_painting_step(bridge, word, rest, step)
    elif word in SOUND_WORDS:                    # the project's sound, Show beats (soundtrack_steps.py)
        do_sound_step(bridge, win, word, rest, step)
    elif word in STROKE_WORDS:                   # Alt picks a colour, the lasso, the focused area (stroke_steps.py)
        do_stroke_step(bridge, win, word, rest, step)
    elif word in DRAG_WORDS:                     # dragtime bar|trim|key|layer|frame [n] [profile] (drag_steps.py)
        do_drag_step(bridge, word, rest, step)
    elif word in STROKE_TIME_WORDS:              # painttime <layer> <x0> <y0> <x1> <y1> [n] (stroke_time.py)
        do_stroke_time(bridge, step, rest)
    elif word in EDIT_WORDS:                     # edittime field|dragend|key|pin|undo [n] (edit_steps.py)
        do_edit_step(bridge, word, rest, step)
    elif word in RIG_WORDS:                      # bones, posing, poses, Lip sync…, Add blinks… (rig_steps.py)
        do_rig_step(bridge, word, rest, step)
    elif word == "canvasreport":                 # canvasreport: print the canvas picture's fingerprint and the history length (hover-preview walks)
        import hashlib
        img = bridge.frames.provider.requestImage("", None, None)
        print(f"canvasreport: canvas {hashlib.md5(bytes(img.constBits())).hexdigest()[:10]} history {bridge.doc.seq} previewing {bridge._previewing}")
    elif word in CLICK_WORDS:                    # clickobj / dragobj: a real click on a named control (click_steps.py)
        do_click_step(win, word, rest, step)
    else:
        raise ValueError(f"unknown step {step!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
