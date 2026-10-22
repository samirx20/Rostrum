"""Scripted steps for the canvas handles (see steps.py): the same bridge calls the handles' drags make. No Qt."""
from __future__ import annotations

import math

HANDLES = {"nw": (-1, -1), "n": (0, -1), "ne": (1, -1), "e": (1, 0), "se": (1, 1), "s": (0, 1), "sw": (-1, 1), "w": (-1, 0)}
MOVES = (0.25, 0.5, 0.75, 1.0)             # a few moves, as a hand would make


def steps_handles(bridge, step, rest):
    word = step.split()[0]
    flags = {"shift": "shift" in rest, "alt": "alt" in rest}
    rest = [r for r in rest if r not in flags]
    if word == "resize":
        bridge.select(rest[0])
        if rest[1] not in HANDLES or not bridge.beginResize(*HANDLES[rest[1]]):
            raise RuntimeError(f"step {step!r}: nothing to resize (handles: {', '.join(HANDLES)})")
        dx, dy = float(rest[2]), float(rest[3])
        for f in MOVES:
            bridge.resizeBy(dx * f, dy * f, flags["shift"], flags["alt"])
        bridge.endDrag()
    elif word == "rotate":
        bridge.select(rest[0])
        if not bridge.beginRotate():
            raise RuntimeError(f"step {step!r}: nothing to rotate")
        b = bridge.selBox
        ox, oy = b["x"] + b["ax"] * b["w"], b["y"] + b["ay"] * b["h"]
        start = math.radians(b["rot"])
        for f in (0.0, *MOVES):                # the pointer circles the anchor by the asked angle
            a = start + math.radians(float(rest[1]) * f)
            bridge.rotateTo(ox + 100 * math.cos(a), oy + 100 * math.sin(a), flags["shift"])
        bridge.endDrag()
    elif word == "boxselect":
        bridge._multi.boxSelect(*[float(v) for v in rest[:4]], " ".join(k for k in ("shift", "ctrl") if flags.get(k) or k in rest))   # [shift] [ctrl]
    elif word == "shiftpick":
        bridge._multi.toggle(rest[0])
    elif word == "movesel":
        if not bridge.beginMove():
            raise RuntimeError(f"step {step!r}: nothing to move")
        dx, dy = float(rest[0]), float(rest[1])
        for f in MOVES:
            bridge.moveBy(dx * f, dy * f)
        bridge.endDrag()
