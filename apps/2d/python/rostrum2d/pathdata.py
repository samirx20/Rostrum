"""Path data (`d`) of path layers: absolute M x y, L x y, C x1 y1 x2 y2 x y, Z only (ENGINE_CONTRACT.md § 2 path).

Two views of one path:
- commands: [("M", x, y), ("L", x, y), ("C", x1, y1, x2, y2, x, y), ("Z",)], what `d` says;
- points: subpaths [{"closed": bool, "points": [{"x", "y", "in": [dx, dy], "out": [dx, dy]}]}], what the pen
  edits: each point with its handles as offsets from it ([0, 0] = no handle, a corner).
Coordinates are the layer's own px from its box's top-left.
"""
from __future__ import annotations

import math
import re

_TOKEN = re.compile(r"[MLCZ]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|[^\s,]")
_COUNT = {"M": 2, "L": 2, "C": 6, "Z": 0}
K = 0.5522847498  # a quarter circle's handle length, as a fraction of its radius


def commands(d: str) -> list[tuple]:
    """`d` → commands. A bad `d` raises ValueError saying what is wrong (as the engine's check, stage_path.rs)."""
    toks, out, i, cmd, open_ = _TOKEN.findall(d), [], 0, None, False
    while i < len(toks):
        if toks[i] in _COUNT:
            cmd, i = toks[i], i + 1
            if cmd == "Z":
                if not open_:
                    raise ValueError("Z before any M")
                out.append(("Z",))
                open_ = False
                continue
        elif cmd in (None, "Z"):
            raise ValueError(f'"{toks[i]}" before a command (absolute M, L, C, Z only)')
        n = _COUNT[cmd]
        nums = toks[i:i + n]
        if len(nums) < n or any(t in _COUNT for t in nums):
            raise ValueError(f"{cmd} needs {n} numbers")
        try:
            vals = [float(t) for t in nums]
        except ValueError:
            raise ValueError(f'"{" ".join(nums)}" are not numbers (absolute M, L, C, Z only)') from None
        if cmd != "M" and not open_:
            raise ValueError(f"{cmd} needs an M first")
        out.append((cmd, *vals))
        open_, i = True, i + n
        if cmd == "M":
            cmd = "L"                                    # more pairs after M are lines
    return out


def write(cmds) -> str:
    return " ".join(c[0] + ("" if len(c) == 1 else " " + " ".join(_num(v) for v in c[1:])) for c in cmds)


def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def check(d: str, where: str = "d") -> str:
    try:
        commands(d)
    except ValueError as e:
        raise ValueError(f"{where}: {e}") from None
    return d


# ---- points (the pen's view) ----

def to_points(d: str) -> list[dict]:
    subs = []
    for c in commands(d):
        if c[0] == "M":
            subs.append({"closed": False, "points": [_pt(c[1], c[2])]})
        elif c[0] == "L":
            subs[-1]["points"].append(_pt(c[1], c[2]))
        elif c[0] == "C":
            pts = subs[-1]["points"]
            prev = pts[-1]
            prev["out"] = [c[1] - prev["x"], c[2] - prev["y"]]
            pts.append(_pt(c[5], c[6], [c[3] - c[5], c[4] - c[6]]))
        else:
            sub = subs[-1]
            sub["closed"] = True
            first, last = sub["points"][0], sub["points"][-1]
            if len(sub["points"]) > 1 and (first["x"], first["y"]) == (last["x"], last["y"]):
                first["in"] = last["in"]                 # a closing curve ends on the first point: one point
                sub["points"].pop()
    return subs


def _pt(x, y, in_=None, out=None) -> dict:
    return {"x": x, "y": y, "in": list(in_ or [0.0, 0.0]), "out": list(out or [0.0, 0.0])}


def from_points(subs: list[dict]) -> str:
    cmds = []
    for sub in subs:
        pts = sub["points"]
        if not pts:
            continue
        cmds.append(("M", pts[0]["x"], pts[0]["y"]))
        pairs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if sub.get("closed") and len(pts) > 1 else [])
        for i, (a, b) in enumerate(pairs):
            closing = sub.get("closed") and i == len(pairs) - 1
            if a["out"] == [0, 0] and b["in"] == [0, 0]:
                if not closing:
                    cmds.append(("L", b["x"], b["y"]))
            else:
                cmds.append(("C", a["x"] + a["out"][0], a["y"] + a["out"][1], b["x"] + b["in"][0], b["y"] + b["in"][1],
                             b["x"], b["y"]))
        if sub.get("closed"):
            cmds.append(("Z",))
    return write(cmds)


def locate(subs: list[dict], n: int) -> tuple[int, int]:
    """The n-th point counted over all subpaths → (subpath, point)."""
    for s, sub in enumerate(subs):
        if n < len(sub["points"]):
            return s, n
        n -= len(sub["points"])
    raise ValueError(f"no point {n} (the path has {sum(len(s['points']) for s in subs)})")


# ---- geometry ----

def transformed(cmds, fn) -> list[tuple]:
    """Every point of the commands through fn(x, y) -> (x, y) (exact for an affine map)."""
    out = []
    for c in cmds:
        xy = [fn(c[i], c[i + 1]) for i in range(1, len(c), 2)]
        out.append((c[0], *[v for p in xy for v in p]))
    return out


def bounds(cmds) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of the drawn curve (cubic extremes, not handles)."""
    xs, ys, cur = [], [], (0.0, 0.0)
    for c in cmds:
        if c[0] == "C":
            for axis, vals in ((0, xs), (1, ys)):
                p = (cur[axis], c[1 + axis], c[3 + axis], c[5 + axis])
                vals += [_cubic(p, t) for t in _extremes(p)]
        if len(c) > 1:
            cur = (c[-2], c[-1])
            xs.append(cur[0])
            ys.append(cur[1])
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def _cubic(p, t):
    u = 1 - t
    return u * u * u * p[0] + 3 * u * u * t * p[1] + 3 * u * t * t * p[2] + t * t * t * p[3]


def _extremes(p):
    a = -p[0] + 3 * p[1] - 3 * p[2] + p[3]
    b = 2 * (p[0] - 2 * p[1] + p[2])
    c = p[1] - p[0]
    if abs(a) < 1e-12:
        roots = [-c / b] if abs(b) > 1e-12 else []
    else:
        disc = b * b - 4 * a * c
        roots = [] if disc < 0 else [(-b + s * math.sqrt(disc)) / (2 * a) for s in (1, -1)]
    return [t for t in roots if 0 < t < 1]


def fit(cmds) -> tuple[list[tuple], tuple[float, float, float, float]]:
    """The commands moved so their bounds start at (0, 0), and (x0, y0, w, h) of the bounds (w, h at least 1)."""
    x0, y0, x1, y1 = bounds(cmds)
    return transformed(cmds, lambda x, y: (x - x0, y - y0)), (x0, y0, max(x1 - x0, 1.0), max(y1 - y0, 1.0))


# ---- shapes and primitives ----

def rect(w: float, h: float, r: float = 0.0, inset: float = 0.0) -> str:
    x0, y0, x1, y1 = inset, inset, w - inset, h - inset
    r = max(0.0, min(r - inset, (x1 - x0) / 2, (y1 - y0) / 2))
    if r == 0:
        return write([("M", x0, y0), ("L", x1, y0), ("L", x1, y1), ("L", x0, y1), ("Z",)])
    k = r * (1 - K)
    return write([("M", x0 + r, y0), ("L", x1 - r, y0), ("C", x1 - k, y0, x1, y0 + k, x1, y0 + r),
                  ("L", x1, y1 - r), ("C", x1, y1 - k, x1 - k, y1, x1 - r, y1), ("L", x0 + r, y1),
                  ("C", x0 + k, y1, x0, y1 - k, x0, y1 - r), ("L", x0, y0 + r), ("C", x0, y0 + k, x0 + k, y0, x0 + r, y0),
                  ("Z",)])


def ellipse(w: float, h: float, inset: float = 0.0) -> str:
    cx, cy, rx, ry = w / 2, h / 2, max(w / 2 - inset, 0), max(h / 2 - inset, 0)
    kx, ky = rx * K, ry * K
    return write([("M", cx, cy - ry), ("C", cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy),
                  ("C", cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry), ("C", cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy),
                  ("C", cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry), ("Z",)])


def star(points: int = 5, outer: float = 100.0, inner: float = 45.0, rotation: float = 0.0) -> str:
    """A star with `points` tips, fitted to its box (first tip straight up, turned by `rotation` degrees)."""
    if points < 2:
        raise ValueError("a star needs at least 2 points")
    return _ring([outer if i % 2 == 0 else inner for i in range(2 * points)], rotation)


def polygon(sides: int = 6, radius: float = 100.0, rotation: float = 0.0) -> str:
    """A regular polygon, fitted to its box (first corner straight up)."""
    if sides < 3:
        raise ValueError("a polygon needs at least 3 sides")
    return _ring([radius] * sides, rotation)


def _ring(radii, rotation) -> str:
    n = len(radii)
    pts = [(r * math.sin(math.radians(rotation + 360 * i / n)), -r * math.cos(math.radians(rotation + 360 * i / n)))
           for i, r in enumerate(radii)]
    cmds = [("M", *pts[0])] + [("L", *p) for p in pts[1:]] + [("Z",)]
    return write(fit(cmds)[0])


def for_script(layer) -> dict:
    """The script layer's names: `path(id, d=…)` (its box from d when w / h are left out) and the primitives
    `star(points, outer, inner, rotation)` and `polygon(sides, radius, rotation)`, which give d."""
    def path(id=None, **values):
        if "d" in values:
            x0, y0, x1, y1 = bounds(commands(check(values["d"], f"{id or 'path'}.d")))
            values.setdefault("w", max(x1, 1.0))
            values.setdefault("h", max(y1, 1.0))
        return layer("path", id, **values)
    return {"path": path, "star": star, "polygon": polygon}
