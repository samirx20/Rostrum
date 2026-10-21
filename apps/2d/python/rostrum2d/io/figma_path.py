"""Figma path data (`fillGeometry[].path`: SVG with absolute M L C Q Z) → ours (M L C Z, moved by an offset)."""
from __future__ import annotations

import re

from .. import pathdata as PD

_TOKEN = re.compile(r"[MLCQZ]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_COUNT = {"M": 2, "L": 2, "C": 6, "Q": 4, "Z": 0}


def to_commands(d: str, dx: float = 0.0, dy: float = 0.0) -> list[tuple]:
    """Figma `d` → commands (Q raised to C), every point moved by (dx, dy). Anything else in `d` raises."""
    left = _TOKEN.sub("", d).replace(",", "").strip()
    if left:
        raise ValueError(f"Figma path data has something this importer can't read: {left[:20]!r}")
    toks, out, i, cmd, cur = _TOKEN.findall(d), [], 0, None, (0.0, 0.0)
    while i < len(toks):
        if toks[i] in _COUNT:
            cmd, i = toks[i], i + 1
        elif cmd in (None, "Z"):
            raise ValueError("Figma path data has numbers before a command")
        n = _COUNT[cmd]
        v = [float(t) for t in toks[i:i + n]]
        if len(v) < n:
            raise ValueError(f"Figma path data: {cmd} needs {n} numbers")
        i += n
        v = [x + (dx, dy)[k % 2] for k, x in enumerate(v)]
        if cmd == "Q":                                   # quadratic → cubic: control points 2/3 of the way to the handle
            (qx, qy, x, y), (px, py) = v, cur
            out.append(("C", px + 2 / 3 * (qx - px), py + 2 / 3 * (qy - py), x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y), x, y))
        else:
            out.append((cmd, *v))
        if v:
            cur = (v[-2], v[-1])
        if cmd == "M":
            cmd = "L"
    return out


def to_d(paths: list[str], dx: float, dy: float) -> str:
    return PD.write([c for p in paths for c in to_commands(p, dx, dy)])
