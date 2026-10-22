"""Scripted steps for the canvas's view (zoom and pan; Stage.qml, CanvasView.qml) and a drag held mid-way (steps.py
hands these over). The view is screen state: these only move what the window shows, never the document.

    zoom <percent|fit> [x y]   the zoom (as the % menu: Fit, or a percent), centred on composition point x y if given
    pan <dx> <dy>              move the view by screen px (as Space+drag)
    viewmenu                   open the "Fit · 50 % ▾" menu
    fitsel                     F: zoom to the selection (nothing selected: everything)
    draghold <layer> <dx> <dy> [ctrl] [shift]   press on a layer and drag it by composition px without letting go
                               (for a picture of the snap lines; ctrl = pressed after the drag began, shift = straight)
"""
from __future__ import annotations

from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QObject

WORDS = ("zoom", "pan", "fitsel", "draghold", "viewmenu")


def _call(win, fn, *args):
    stage = win.findChild(QObject, "stage")
    if stage is None:
        raise RuntimeError("no canvas in the window (objectName 'stage')")
    QMetaObject.invokeMethod(stage, fn, *(Q_ARG("QVariant", a) for a in args))
    QCoreApplication.processEvents()


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
    elif word == "viewmenu":
        _call(win, "openViewMenu")
    elif word == "fitsel":
        _call(win, "fitSelection")
    elif word == "draghold":
        bridge.select(rest[0])
        if not bridge.beginMove():
            raise RuntimeError(f"step {step!r}: nothing to move")
        bridge.snap.keys("ctrl" in rest[3:], "shift" in rest[3:])
        dx, dy = float(rest[1]), float(rest[2])
        for f in (0.25, 0.5, 0.75, 1.0):
            bridge.moveBy(dx * f, dy * f)
        print("snapped to:", bridge.snap.lines)
