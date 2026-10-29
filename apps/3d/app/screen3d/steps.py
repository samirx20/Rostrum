"""Scripted steps for screenshots and checks. Each goes through the same bridge (or viewport) call a click or drag makes.

    select <id> | selectmany <id> <id> … (the first is the base) | deselect (nothing selected: the Scene) | action <id> (a settings panel action, e.g. combine:subtract)
    preview <id> / unpreview (the hover preview of a panel action: what resting the pointer on it shows; leaving) | frame <n> | set <param> <json value> | scrub <param> <v> <v> … | animate <param> (the key mark)
    curves on|off|all|mine | curvedrag <key> <dt s> <dv> | handledrag <key> <1|2> <dx> <dy> (the timeline's Curves: curve_steps.py)
    keydrag <key id> <frame> | keys-stretch <grabbed key> <frame> <picked key> … | keys-menu <key id> (key_steps.py) | stretch <key id> (a click on the stretch it starts) | ease <preset> (the animation panel's) | press <Tab | K | Return | Alt+Z …> (a real key) | fold <id> | undo | redo | more | commands [query …] | run <command key> | play
    context <item id | -> (the right-click menu) | lipsync <mouth group id> (its Lip sync… sheet) | showshot <shot id> (the crumb's pick) | shot-from-view (its New shot from this view)
    add <menu value, e.g. mesh:sphere | light:distant | camera | material | shot> | duplicate | delete
    arm <mesh:box …> [field=value …] (a shape picked in the Shapes or Type & logo flyout, with its source for a logo:
    svgFile=<path> or doc2d=<id> layer=<id>; the next viewport click (`mouseclick`, `viewclick`) places it on the surface there)
    type <words …> (real keys into a 3D text just placed: live, one undo step) | typeend (Esc ends the typing)
    (a click in the viewport by real input: the kit's `mouseclick <x> <y>`, window pixels)
    import-hover | import-note | import-file | import-drop (imports: import_steps.py)
    drawings (From a 2D drawing's list of 2D items) | drawing <doc2d> (its path layers: the list's second level)
    wait <ms> | settled (until the newest picture is in and the engine idle) | snap <png path> (a screenshot now, the run goes on)
    rail <shapes|type|lights|camera> (opens that flyout) | page build|animate|render | materials | shots | view (open the
    header's menus) | picker (the selected item's material picker) | startfrom <start> | split (Make its own) | assign <material id> | mouse <x> <y> (a click on the window) | renderstart | cancelrender (both don't wait)
    render (Cycles, the playhead frame; waits for the job, up to 10 min) | closerender
    sim-demo <not computed | running | stored | out of date | failed> (the timeline's Simulate row, never a simulation)
    render-sheet (the render sheet: the ▾ beside Render, Ctrl+E) | render-demo <running | done> (the header's Render, never a render) | estimate-recorded (its time from a fixed, recorded measurement: never a probe) |
    estimate-wait (until its time is measured) | budget <time, e.g. 10 min> | sheet-format png|exr|both (its Save as: a shot edit)
    sheet-render (the sheet's Render; waits for the job, up to 10 min)
    queue add <shot> [first] | move <row> <index> | cancel <row> | show <row> | wait-frames <n> | wait-idle | report | demo
    (the Render page's queue: queue_steps.py)
  Viewport (screen state, never the document): orbit <dx> <dy> | pan <dx> <dy> | zoom <steps> | mode shot|free
    exposure <stops> | studio <amount> | lights on|off | home | viewclick <x> <y> (viewport pixels: selects what is there, places the armed shape,
    or, while placing or linking a light, that; named apart from the kit's `click <text>`, which runs first)
    look quick|final (Final: progressive Cycles in place; `wait` lets it refine)
  Gizmo (real mouse input on the window): gizmo-drag <handle: move0..2 | plane | turn0..2 | scale0..2> <dx> <dy> [ctrl]
    (press on that handle, move by dx dy screen px in 8 steps, release) | gizmo-show all|move|turn|scale | key-moved
  Edit mesh: mesh-tab | mesh-edit | mesh-kind | mesh-pick | mesh-box | mesh-action | mesh-number | mesh-arrow | mesh-material | mesh-xray | mesh-knife* | mesh-esc (mesh_steps.py)
  Paint: paint-b | paint-layer | paint-channel | paint-brush | paint-drag (paint_steps.py)
A step that leaves an error in the status fails (nonzero exit).
"""
from __future__ import annotations

import functools, json, operator, time  # noqa: E401

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QObject, QPoint, QPointF, Qt
from rostrum_gui import curve_steps
from rostrum_gui.lazy_qtest import QTest   # never at import: a person's launch must not count as scripted (lazy_qtest.py)
from rostrum_gui.settle import save_snap

RENDER_WAIT_S = 600
PAINT_DRAG_S = 20                                     # a paint-drag waits for one engine pick per point


def step_waits_ms(steps) -> int:
    """The time a scripted run's steps may take on purpose (their `wait`s, a render, a paint drag's picks): the run's
    timeout adds it to its own 30 s, so a long walk is never cut short while a hung one still fails."""
    words = [s.split() for s in steps if s.strip()]
    return (sum(int(w[1]) for w in words if w[0] == "wait" and len(w) > 1)
            + (RENDER_WAIT_S * 1000 if any(w[0].startswith("render") or w[0] == "sheet-render" for w in words) else 0)
            + PAINT_DRAG_S * 1000 * sum(w[0] == "paint-drag" for w in words))


VIEW = {"orbit": lambda v, a: v.orbit(float(a[0]), float(a[1])), "pan": lambda v, a: v.pan(float(a[0]), float(a[1])),
        "zoom": lambda v, a: v.zoom(float(a[0])), "mode": lambda v, a: v.setMode(a[0]),
        "exposure": lambda v, a: v.setExposure(float(a[0])), "studio": lambda v, a: v.setStudio(float(a[0])),
        "lights": lambda v, a: v.setSceneLights(a[0] == "on"), "home": lambda v, a: v.home(),
        "viewclick": lambda v, a: v.click(float(a[0]), float(a[1])), "look": lambda v, a: v.setLook(a[0])}


def recorded_estimate() -> dict:
    """A measurement as estimate_job keeps one (the reference laptop, full HD, good = 128 samples, 2026-10-24), with a
    plain grey picture: the layout check's render sheet, fast and the same every run."""
    import tempfile
    from pathlib import Path
    from PySide6.QtGui import QColor, QImage
    png = Path(tempfile.gettempdir()) / "rostrum3d_recorded_probe.png"
    if not png.is_file():
        img = QImage(960, 540, QImage.Format_RGB32)
        img.fill(QColor("#3a3c42"))
        img.save(str(png))
    return {"frame": 12, "samples": 128, "curve": [[8, 0.27], [128, 1.0]], "load_ms": 900.0, "warmup_ms": 2500.0,
            "fixed_ms": -1200.0, "per_px_ms": 0.0095, "probe": {"size": [960, 540], "ms": [2500.0, 3700.0], "few_ms": 700.0},
            "full": {"size": [1920, 1080], "samples": 8, "ms": 5000.0, "at_job_samples_ms": 18500.0}, "probe_s": 12.0,
            "measured_at": "2026-10-24T05:00:00", "gpu_busy": "", "picture": str(png), "cached": True}


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
        bridge.keyDragTo(float(rest[1]) / bridge.shot_info()["fps"])
        bridge.endDrag()
    elif word in curve_steps.WORDS:            # curves on|off|all|mine | curvedrag … | handledrag … (the kit's curve_steps.py)
        curve_steps.step(bridge.curves, step, rest)
    elif word == "fold":
        bridge.toggleFold(rest[0])
    elif word == "press":                      # a real key on the window: press Tab | K | Return | Escape | 2 | Alt+Z
        *mods, key = rest[0].split("+")
        m = functools.reduce(operator.or_, (getattr(Qt.KeyboardModifier, n.capitalize() + "Modifier") for n in mods), Qt.KeyboardModifier.NoModifier)
        QTest.keyClick(win, getattr(Qt.Key, "Key_" + key), m)
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
    elif word == "showshot":
        bridge.showShot(rest[0])
    elif word == "shotonly":                   # shotonly on | off: the settings' Changes switch (bridge_shot_only.py)
        bridge.setShotOnly(rest[0] == "on")
    elif word == "shot-from-view":
        bridge.newShotFromView()
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
    elif word.startswith("import-"):   # import-hover | import-note | import-file | import-drop (import_steps.py)
        from . import import_steps
        import_steps.do(bridge, win, step)
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
    elif word == "lipsync":        # lipsync <mouth group id>: the right-click menu's Lip sync… (lipsync3d.py)
        bridge.open_lipsync(rest[0])
    elif word == "assets":         # assets [sample]: Import › Asset library (assets_qt.py); sample = Poly Haven on, a fixed offline list
        bridge.assets.use_sample() if rest[:1] == ["sample"] else bridge.assets.open()
    elif word == "rail":
        QMetaObject.invokeMethod(win, "openRailGroup", Q_ARG("QVariant", rest[0]))
    elif word == "panel":          # panel poses | onion: the Animate rail's own small panels (Rail3D.qml)
        QMetaObject.invokeMethod(win, "openRailPanel", Q_ARG("QVariant", rest[0]))
    elif word == "pose":           # pose <name…>: Save pose from the selection at the playhead (poses_qt.py)
        bridge.poses.save(" ".join(rest))
    elif word == "onion":          # onion on | off | keys | frames (onion_qt.py)
        o = bridge.viewport.onion
        o.setOn(rest[0] != "off") if rest[0] in ("on", "off") else o.setMode(rest[0])
    elif word == "page":
        bridge.setPage(rest[0])
    elif word == "stretch":        # stretch <key id>: the click on the stretch that key starts (its item's, StretchBand.qml)
        bridge.stretch.pick(bridge.doc.parent_of(rest[0])[0], [rest[0]])
    elif word == "ease":           # ease <linear | smooth | in | out | spring | bounce | hold>: a preset in the animation panel
        if not bridge.stretch.setEase(rest[0]):
            raise RuntimeError(f"step {step!r}: no stretch picked, or {bridge.status}")
    elif word == "startfrom":
        bridge.mats.startFrom(" ".join(rest))
    elif word == "assign":
        bridge.mats.assign(rest[0])
    elif word == "split":
        bridge.mats.split()
    elif word in ("materials", "shots", "view", "picker"):
        QMetaObject.invokeMethod(win, "open" + word.capitalize())
    elif word == "mouse":
        QTest.qWait(400)                              # let the last step lay out
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(int(rest[0]), int(rest[1])))
    elif word == "wait":
        QTest.qWait(int(rest[0]))
    elif word == "settled":                        # until the newest picture is in and the engine is idle (a key sent
        v = bridge.viewport                        # to a window that has drawn nothing yet is lost; a new clay takes
        QTest.qWait(50)                            # its build before it shows; a key's action runs a frame later),
        for _ in range(1500):                      # at most 30 s, else loudly
            if v.serial > 0 and v._r.idle() and not v._next.isActive():
                break
            QTest.qWait(20)
        else:
            raise RuntimeError(f"step {step!r}: the viewport did not settle within 30 s ({v.status or 'no status'})")
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
    elif word == "render-demo":                   # the header's running Render, or its finished picture (never a render)
        bridge.render.demo(rest[0], recorded_estimate()["picture"])
    elif word == "sim-demo":                      # the Simulate row in a fixed state (sim_qt.ROW_STATES; never a simulation)
        bridge.sim.demo(" ".join(rest))
    elif word == "closerender":
        bridge.render.dismiss()
    elif word == "gizmo-drag":
        _gizmo_drag(bridge, win, rest[0], float(rest[1]), float(rest[2]), "ctrl" in rest[3:])
    elif word == "gizmo-show":
        bridge.viewport.gizmo.setShow(rest[0])
    elif word == "key-moved":
        bridge.viewport.gizmo.keyMoved()
    elif word == "queue":                         # the Render page's queue (queue_steps.py)
        from . import queue_steps
        queue_steps.do(bridge, rest)
    elif word.startswith("keys-"):                # picked keys: Alt+drag stretch, the right-click Ease list (key_steps.py)
        from . import key_steps
        key_steps.do(bridge, win, word, rest)
    elif word.startswith("mesh-"):                # Edit mesh (mesh_steps.py)
        from . import mesh_steps
        mesh_steps.do(bridge, word, rest)
    elif word.startswith("paint-"):               # Paint mode (paint_steps.py)
        from . import paint_steps
        paint_steps.do(bridge, win, word, rest)
    elif word == "render-sheet":
        bridge.exporter.openFor()
    elif word == "estimate-recorded":
        bridge.exporter.estimate.use_recorded(recorded_estimate())
    elif word == "estimate-wait":
        from .estimate_sheet import DEADLINE_S
        est = bridge.exporter.estimate
        for _ in range(int(DEADLINE_S + 10) * 10):    # the 0.4 s wait, the probe on its own thread, its deadline
            QCoreApplication.processEvents()
            if est.state in ("ready", "failed"):
                break
            QTest.qWait(100)
        if est.state != "ready":
            raise RuntimeError(f"step {step!r}: the estimate is {est.state!r}: {est.text}")
    elif word == "budget":
        if why := bridge.exporter.estimate.setBudget(" ".join(rest)):
            raise RuntimeError(f"step {step!r}: {why}")
    elif word == "sheet-format":
        bridge.exporter.setFormat(rest[0])
    elif word == "sheet-render":
        sheet, t0 = bridge.exporter, time.monotonic()
        said = sheet.estimate.text
        sheet.request()
        if not sheet.wait(RENDER_WAIT_S) or sheet.state != "done":
            raise RuntimeError(f"step {step!r}: {sheet.state}: {sheet.note}")
        print(f"sheet-render: the sheet said {said!r}; rendered in {time.monotonic() - t0:.1f} s: {sheet.path}", flush=True)
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
