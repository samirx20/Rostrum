"""Scripted Paint mode steps (steps.py hands every `paint-…` word here), each the same call a key, click or drag makes:

    paint-b (B: Paint in / out; unfolds a mesh with no unfolded surface) | paint-layer (the + of Paint layers)
    paint-channel colour|roughness|height|metal|glow (the active layer's Paints) | paint-brush <setting> <value>
    (a Brush row: brush, size, color, opacity) | paint-where surface|view (On the surface | From the view) |
    paint-tint (the coverage tint on / off) | paint-how stroke|stamp (Brush | Stamp, on a Relief layer) |
    paint-load <picture file> (the stamp's Picture › Load picture…, the file handed in as its dialog would) |
    paint-click <x> <y> (a real left click on the viewport there, in parts of it: a Stamp) | paint-drag <x0> <y0> <x1> <y1> [steps] [<x2> <y2> …] (a real left
    drag on the window through those points of the viewport, in parts of it, 0..1; each move waits for its pick)
"""
from __future__ import annotations

import time

from PySide6.QtCore import QCoreApplication


def _settle(pm, timeout=20.0):
    end = time.monotonic() + timeout
    while pm._busy:
        if time.monotonic() > end:
            raise RuntimeError("paint-drag: the engine did not answer a pick in time")
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _path(nums: list[float], steps: int) -> list[tuple[float, float]]:
    corners = list(zip(nums[0::2], nums[1::2]))
    out = [corners[0]]
    for (ax, ay), (bx, by) in zip(corners, corners[1:]):
        out += [(ax + (bx - ax) * i / steps, ay + (by - ay) * i / steps) for i in range(1, steps + 1)] if steps else []
    return out


def do(bridge, win, word, rest):
    pm = bridge.viewport.paint
    if word == "paint-click":                        # a click: a drag that never moves
        word, rest = "paint-drag", [rest[0], rest[1], rest[0], rest[1], "0"]
    if word == "paint-b":
        pm.toggle()
        QCoreApplication.processEvents()
        time.sleep(0.05)
        QCoreApplication.processEvents()                 # the unfold runs just after the mode opens
    elif word == "paint-layer":
        pm.addLayer()
    elif word == "paint-where":
        pm.setWhere(rest[0])
    elif word == "paint-how":
        pm.setHow(rest[0])
    elif word == "paint-load":
        from pathlib import Path
        if not pm.brush.loadChoice("texture", str(Path(rest[0]).resolve())):
            raise RuntimeError(f"paint-load: {rest[0]} was refused ({bridge.status})")
    elif word == "paint-tint":
        pm.coverage.toggle()
    elif word == "paint-channel":
        pm.setChannel(rest[0])
    elif word == "paint-brush":
        value = rest[1] if rest[0] in ("brush", "color") else float(rest[1])
        if not pm.brush.setValue(rest[0], value):
            raise RuntimeError(f"paint-brush: {rest[0]} {rest[1]} was refused")
    elif word == "paint-drag":                       # real mouse input on the window, as a person drags
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtQuick import QQuickItem
        from PySide6.QtTest import QTest
        nums = [float(v) for v in rest]
        steps = int(nums.pop(4)) if len(nums) % 2 else 12   # x0 y0 x1 y1 steps [x2 y2 …]; steps 0: a click
        item = win.findChild(QQuickItem, "viewport3d")
        pts = [item.mapToScene(QPointF(fx * item.width(), fy * item.height())) for fx, fy in _path(nums, steps)]
        at = [QPoint(round(p.x()), round(p.y())) for p in pts]
        QTest.mouseMove(win, at[0])
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, at[0])
        for p in at[1:]:
            _settle(pm)
            QTest.mouseMove(win, p)
            QTest.qWait(10)
        _settle(pm)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, at[-1])
        _settle(pm, 60.0)
    else:
        raise ValueError(f"unknown step {word!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {word}: {bridge.status}")
