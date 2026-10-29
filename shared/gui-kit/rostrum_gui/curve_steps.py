"""The curve view's screen steps, the same in every app (2D steps.py, 3D steps.py): curves on|off|all|mine,
curvedrag <key> <dt s> <dv value>, handledrag <key> <1|2> <dx> <dy> (dx, dy: change of that handle's x / y in the
curve's own 0..1 units). Each drag moves in two steps, as a hand would, and is one undo step (curve_view.py)."""
from __future__ import annotations

from .curve_view import X, Y

WORDS = ("curves", "curvedrag", "handledrag")


def step(cv, step: str, rest: list[str]) -> None:
    word = step.split()[0]
    if word == "curves":
        if rest[0] in ("all", "mine"):
            cv.setAll(rest[0] == "all")
        else:
            cv.setOn(rest[0] == "on")
        return
    key = cv.item(rest[0])          # 2D: placed (keys on a marker at their seconds)
    if word == "curvedrag":
        cv.beginKeyDrag(key["id"])
        for f in (0.5, 1.0):
            cv.keyTo(key["t"] + float(rest[1]) * f, key["v"] + float(rest[2]) * f)
    else:
        which, dx, dy = int(rest[1]), float(rest[2]), float(rest[3])
        if not cv.beginHandleDrag(key["id"], which):
            raise RuntimeError(f"step {step!r}: that key has no handles on its stretch")
        g = cv._grab
        (t0, v0), (t1, v1), h = g["p0"], g["p3"], g["h"]
        x0, y0 = h[X[which - 1]], h[Y[which - 1]]
        for f in (0.5, 1.0):
            cv.handleTo(t0 + (x0 + dx * f) * (t1 - t0), v0 + (y0 + dy * f) * (v1 - v0))
    cv.endDrag()
