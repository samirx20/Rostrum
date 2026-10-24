"""`painttime`: what a brush stroke costs the screen, through the calls the pen makes (painter.beginStroke, strokeTo,
endStroke), on any layer the pen can paint (its own paint, or its painted fill in place).

    painttime <layer> <x0> <y0> <x1> <y1> [n]
        The layer picked, the Brush on, a stroke from (x0, y0) to (x1, y1) (composition px) in n moves (default 60), one
        per screen refresh: the press's and each move's busy time on the screen's thread (the wet ink included), the
        release's, and the ms from the release until the picture with the stroke has landed (every layer using a
        painting shows it then). The stroke stays (Ctrl+Z takes it back).
    painthold <x> <y> <x> <y> …
        A stroke through those points (composition px) on what the pen paints on now, the pen left down: a picture
        then shows the wet ink as it is while painting (on every layer using a painting).
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import QCoreApplication

from .drag_steps import PACE_MS, Busy, _spread, _wait
from .edit_steps import _Pictures, _settle

WORDS = ("painttime", "painthold")


def do_stroke_time(bridge, step, rest):
    if step.split()[0] == "painthold":
        pts = [float(v) for v in rest]
        if not bridge.painter.beginStroke(pts[0], pts[1], 1.0):
            raise RuntimeError(f"step {step!r}: the stroke didn't start: {bridge.status}")
        px, py = pts[0], pts[1]
        for x, y in zip(pts[2::2], pts[3::2]):
            for i in range(1, 9):               # several moves per segment, as a pen sends them
                bridge.painter.strokeTo(px + (x - px) * i / 8, py + (y - py) * i / 8, 1.0)
                QCoreApplication.processEvents()
            px, py = x, y
        return
    layer, (x0, y0, x1, y1), n = rest[0], (float(v) for v in rest[1:5]), int(rest[5]) if len(rest) > 5 else 60
    bridge.select(layer)
    bridge.paintTool.use("brush")
    _wait(300)                                   # what picking set off settles first
    busy, pics = Busy(), _Pictures(bridge)
    try:
        b0 = busy.now()
        if not bridge.painter.beginStroke(x0, y0, 1.0):
            raise RuntimeError(f"step {step!r}: the stroke didn't start: {bridge.status}")
        QCoreApplication.processEvents()
        press, ms = busy.now() - b0, []
        for i in range(1, n + 1):
            t0, b0 = time.perf_counter(), busy.now()
            bridge.painter.strokeTo(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n, 1.0)
            QCoreApplication.processEvents()
            _wait(PACE_MS - (time.perf_counter() - t0) * 1000)
            ms.append(busy.now() - b0)
        pics.arm()
        t0, b0 = time.perf_counter(), busy.now()
        bridge.painter.endStroke()
        QCoreApplication.processEvents()
        release = busy.now() - b0
        _settle(pics, "painttime")
        landed = (pics.last_ready - t0) * 1000
    finally:
        pics.close()
        busy.close()
    print(f"painttime {layer} ({bridge.painter.selectedItem.get('kindLabel', '')}): press {press:.1f} ms; {n} moves, "
          f"screen thread busy per move {_spread(ms)}; release {release:.1f} ms; picture with the stroke landed "
          f"{landed:.0f} ms after the release", flush=True)
    if os.environ.get("ROSTRUM2D_DRAG_SERIES") == "1":
        print("  per move: " + " ".join(f"{m:.0f}" for m in ms))
