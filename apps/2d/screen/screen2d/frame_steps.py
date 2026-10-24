"""Scripted steps for the frame on the canvas (camera spec § 6, CLI screen steps), through the same slots
FrameHandles.qml calls (backend.frameDrag: frame_drag.py), so a check or an agent drives exactly what a person does.

    frame next|prev              frame by frame: the drawing's next / previous drawing (painter.goFrame)
    frame pick                   C: pick the frame
    frame drag <dx> <dy>         drag inside it by world px (one change)
    frame corner <dx>            drag its bottom-right square outward by dx world px (bigger box = zoom down)
    frame turn <deg>             drag a turn zone round its centre by deg degrees
    frametime drag|zoom|turn [n] n pointer moves of that drag (default 60), each waited out: prints each move's
                                 GUI-thread ms, its time to the picture that shows it, and the release's
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QCoreApplication

from . import frame_view
from .playstats import STATS
from .view_steps import _picture, _spread

WORDS = ("frame", "frametime")


def _box(bridge) -> dict:
    return frame_view.box_at(bridge.placed(), bridge._t)


def _gesture(bridge, kind: str, amount: float):
    """(press point, the pointer at fraction f of the drag): a move of `amount` px across, a corner pulled `amount` px
    out along its diagonal, a turn of `amount` degrees."""
    b = _box(bridge)
    cx, cy, r = b["cx"], b["cy"], math.radians(b["rot"])
    if kind == "drag":
        return 0, (cx, cy), lambda f: (cx + amount * f, cy)
    if kind == "zoom":
        hw, hh = b["w"] / 2, b["h"] / 2
        d = math.hypot(hw, hh)
        ux, uy = (math.cos(r) * hw - math.sin(r) * hh) / d, (math.sin(r) * hw + math.cos(r) * hh) / d
        px, py = cx + ux * d, cy + uy * d
        return 2, (px, py), lambda f: (px + ux * amount * f, py + uy * amount * f)
    arm = b["w"] / 2
    return 1, (cx + arm, cy), lambda f: (cx + arm * math.cos(math.radians(amount * f)), cy + arm * math.sin(math.radians(amount * f)))


def _begin(bridge, kind, amount):
    corner, (px, py), at = _gesture(bridge, kind, amount)
    if not bridge.frameDrag.begin({"drag": "move", "zoom": "zoom", "turn": "turn"}[kind], px, py, corner):
        raise RuntimeError(f"frame {kind}: {bridge.status}")
    return (px, py), at


def _to(bridge, kind, p0, p):
    fd = bridge.frameDrag
    if kind == "drag":
        fd.moveBy(p[0] - p0[0], p[1] - p0[1])
    elif kind == "zoom":
        fd.zoomTo(p[0], p[1], False)
    else:
        fd.turnTo(p[0], p[1], False)


def _drag(bridge, kind, amount, n=1):
    p0, at = _begin(bridge, kind, amount)
    for i in range(1, n + 1):
        _to(bridge, kind, p0, at(i / n))
    bridge.frameDrag.end()


def frame_time(bridge, kind, n):
    """`frametime`: n moves of one frame drag, each one's GUI-thread time and its time to the picture showing it."""
    STATS.reset()
    STATS.on = True
    amount = {"drag": 600.0, "zoom": 300.0, "turn": 30.0}[kind]
    p0, at = _begin(bridge, kind, amount)
    gui, shown = [], []
    for i in range(1, n + 1):
        t0 = time.perf_counter()
        _to(bridge, kind, p0, at(i / n))
        QCoreApplication.processEvents()
        gui.append((time.perf_counter() - t0) * 1000)
        if _picture(bridge):
            shown.append((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter()
    bridge.frameDrag.end()
    full = (time.perf_counter() - t0) * 1000 if _picture(bridge, 2000) else None
    px = STATS.ms.get("pixels", [])
    print(f"frametime {kind}: {n} moves; GUI thread {_spread(gui)}; move to picture {_spread(shown)} ({len(shown)} shown); "
          f"engine {_spread(px)}; release to full picture {full and round(full, 1)} ms")
    STATS.on = STATS.log


def do_frame_step(bridge, word, rest, step):
    if word == "frametime":
        return frame_time(bridge, rest[0], int(rest[1]) if rest[1:] else 60)
    what = rest[0]
    if what in ("next", "prev"):                 # frame next|prev: a drawing's next / previous drawing (frame by frame)
        bridge.painter.goFrame(1 if what == "next" else -1)
    elif what == "pick":
        bridge.frameDrag.pick()
    elif what == "drag":
        _drag_by(bridge, float(rest[1]), float(rest[2]))
    elif what == "corner":
        _drag(bridge, "zoom", float(rest[1]))
    elif what == "turn":
        _drag(bridge, "turn", float(rest[1]))
    else:
        raise ValueError(f"unknown step {step!r} (frame pick | drag <dx> <dy> | corner <dx> | turn <deg>)")


def _drag_by(bridge, dx, dy):
    b = _box(bridge)
    if not bridge.frameDrag.begin("move", b["cx"], b["cy"], 0):
        raise RuntimeError(f"frame drag: {bridge.status}")
    bridge.frameDrag.moveBy(dx, dy)
    bridge.frameDrag.end()
