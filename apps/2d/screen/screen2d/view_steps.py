"""Scripted steps for the canvas's view (zoom and pan; Stage.qml, CanvasView.qml) and a drag held mid-way (steps.py
hands these over). The view is screen state: these only move what the window shows, never the document.

    zoom <percent|fit> [x y]   the zoom (as the % menu: Fit, or a percent), centred on composition point x y if given
    pan <dx> <dy> [hold]       move the view by screen px (as Space+drag); hold: again after the next refit (layout check)
    viewmenu                   open the "Fit · 50 % ▾" menu
    fitsel                     F: zoom to the selection (nothing selected: everything)
    fitall                     Shift+1: zoom to everything (every layer and the frame's whole path)
    draghold <layer> <dx> <dy> [ctrl] [shift]   press on a layer and drag it by composition px without letting go
                               (for a picture of the snap lines; ctrl = pressed after the drag began, shift = straight)
    viewtime pan <n> <dx> <dy> | zoom <n> <factor> | drag <layer> <n> <dx> <dy>   n view steps (or n moves of a layer
                               drag, then its release), each waited out: prints each step's GUI-thread time, its time
                               to the window's next frame, the world pictures drawn meanwhile (count, engine ms) and,
                               dragging, each move's time to the picture that shows it
"""
from __future__ import annotations

import statistics
import time

from PySide6.QtCore import Q_ARG, QCoreApplication, QEventLoop, QMetaObject, QObject, QTimer

from .playstats import STATS

WORDS = ("zoom", "pan", "fitsel", "fitall", "draghold", "viewmenu", "viewtime")


def _call(win, fn, *args):
    stage = win.findChild(QObject, "stage")
    if stage is None:
        raise RuntimeError("no canvas in the window (objectName 'stage')")
    QMetaObject.invokeMethod(stage, fn, *(Q_ARG("QVariant", a) for a in args))
    QCoreApplication.processEvents()


def _pan_after_next_fit(win, dx, dy):
    """Pan again once, right after the next layout refit (AppShell.layoutChanged: Main.qml fits the frame on it)."""
    def again():
        win.layoutChanged.disconnect(again)
        _call(win, "panBy", dx, dy)
    win.layoutChanged.connect(again)


def do_view_step(bridge, win, word, rest, step):
    if word == "zoom":
        if rest[0] == "fit":
            _call(win, "fitAll")
        else:
            _call(win, "zoomPercent", float(rest[0].rstrip("%")))
        if rest[1:]:
            _call(win, "centreOn", float(rest[1]), float(rest[2]))
    elif word == "pan":
        _call(win, "panBy", float(rest[0]), float(rest[1]))
        if "hold" in rest[2:]:      # the layout check resizes the window after the steps, and the frame is fitted again then
            _pan_after_next_fit(win, float(rest[0]), float(rest[1]))
    elif word == "viewmenu":
        _call(win, "openViewMenu")
    elif word == "viewtime":
        view_time(bridge, win, rest)
    elif word == "fitsel":
        _call(win, "fitSelection")
    elif word == "fitall":                       # Shift+1: every layer and the frame's whole path
        _call(win, "fitEverything")
    elif word == "draghold":
        bridge.select(rest[0])
        if not bridge.beginMove():
            raise RuntimeError(f"step {step!r}: nothing to move")
        bridge.snap.keys("ctrl" in rest[3:], "shift" in rest[3:])
        dx, dy = float(rest[1]), float(rest[2])
        for f in (0.25, 0.5, 0.75, 1.0):
            bridge.moveBy(dx * f, dy * f)
        print("snapped to:", bridge.snap.lines)


def _shown_next(win, timeout_ms=100) -> bool:
    """Waits for the window's next frame on screen; False when none came (a window covered by others draws nothing)."""
    loop, got = QEventLoop(), []
    done = lambda: (got.append(1), loop.quit())         # noqa: E731
    win.frameSwapped.connect(done)
    QTimer.singleShot(timeout_ms, loop.quit)
    win.requestUpdate()
    loop.exec()
    win.frameSwapped.disconnect(done)
    return bool(got)


def _spread(ms: list[float]) -> str:
    if not ms:
        return "none"
    q = sorted(ms)
    return f"median {statistics.median(q):.1f}, p95 {q[max(0, int(len(q) * 0.95) - 1)]:.1f}, max {q[-1]:.1f} ms"


def view_time(bridge, win, rest):
    """`viewtime`: each view step's work on the GUI thread (the bindings, the overlays, asking for a picture), its
    time to the next frame on screen (when the window is drawn at all), and what the engine drew meanwhile."""
    if rest[0] == "drag":
        return drag_time(bridge, win, rest[1], int(rest[2]), float(rest[3]), float(rest[4]))
    n = int(rest[1])
    STATS.reset()
    STATS.on, pictures = True, []
    bridge.world.changed.connect(lambda: pictures.append(time.perf_counter()))
    gui, screen = [], []
    for _ in range(n):
        t0 = time.perf_counter()
        if rest[0] == "pan":
            _call(win, "panBy", float(rest[2]), float(rest[3]))
        else:
            z = win.findChild(QObject, "stage").property("compScale")
            _call(win, "zoomPercent", z * 100 * float(rest[2]))
        gui.append((time.perf_counter() - t0) * 1000)
        if _shown_next(win):
            screen.append((time.perf_counter() - t0) * 1000)
    t_end = time.perf_counter() + 1.0
    while time.perf_counter() < t_end:            # the last picture settles
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    px = STATS.ms.get("pixels", [])
    print(f"viewtime {rest[0]}: {n} steps; GUI thread {_spread(gui)}; to screen ({len(screen)} drawn) {_spread(screen)}; "
          f"world pictures {len(px)}, engine {_spread(px)}; pictures shown {len(pictures)}")
    STATS.on = STATS.log


def _picture(bridge, timeout_ms=500) -> bool:
    """Waits for the next picture on the canvas."""
    loop, got = QEventLoop(), []
    done = lambda: (got.append(1), loop.quit())         # noqa: E731
    bridge.world.changed.connect(done)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    bridge.world.changed.disconnect(done)
    return bool(got)


def drag_time(bridge, win, layer, n, dx, dy):
    """`viewtime drag`: n moves of a layer drag, each one's GUI-thread time and its time to the picture showing it,
    then the release's time to the full-size picture."""
    STATS.reset()
    STATS.on = True
    bridge.select(layer)
    if not bridge.beginMove():
        raise RuntimeError(f"viewtime drag: {layer} can't be moved")
    gui, shown = [], []
    for i in range(1, n + 1):
        t0 = time.perf_counter()
        bridge.moveBy(dx * i / n, dy * i / n)
        QCoreApplication.processEvents()
        gui.append((time.perf_counter() - t0) * 1000)
        if _picture(bridge):
            shown.append((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter()
    bridge.endDrag()
    full = (time.perf_counter() - t0) * 1000 if _picture(bridge, 2000) else None
    px = STATS.ms.get("pixels", [])
    print(f"viewtime drag {layer}: {n} moves; GUI thread {_spread(gui)}; move to picture {_spread(shown)}; "
          f"engine {_spread(px)}; release to full picture {full and round(full, 1)} ms")
    STATS.on = STATS.log
