"""Path data (`d`) of path layers: stored as absolute M x y, L x y, C x1 y1 x2 y2 x y, Z only (ENGINE_CONTRACT.md § 2
path). What people and agents give may be any SVG path data (relative commands, H, V, Q, T, S, A arcs): `normalize`
turns it into those four at the input boundary (a script's path(d=) and d keys, path.set, key.add), exactly for
lines, quadratics and smooth curves, arcs as cubics within 0.03 % of their radius.

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
            raise ValueError(f'"{toks[i]}" before a command (start with M)')
        n = _COUNT[cmd]
        nums = toks[i:i + n]
        if len(nums) < n or any(t in _COUNT for t in nums):
            raise ValueError(f"{cmd} needs {n} numbers")
        try:
            vals = [float(t) for t in nums]
        except ValueError:
            raise ValueError(f'"{" ".join(nums)}" are not numbers') from None
        if cmd != "M" and not open_:
            raise ValueError(f"{cmd} needs an M first")
        out.append((cmd, *vals))
        open_, i = True, i + n
        if cmd == "M":
            cmd = "L"                                    # more pairs after M are lines
    return out


_NUM = re.compile(r"[\s,]*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")
_FLAG = re.compile(r"[\s,]*([01])")
_GAP = re.compile(r"[\s,]*")
_SVG_COUNT = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
_STORED = re.compile(r"[\sMLCZ0-9eE.,+-]*")


def normalize(d: str) -> str:
    """Any SVG path data → absolute M, L, C, Z (as stored and drawn). Already only those: returned as given. Anything
    else SVG does not read (an unknown letter, a missing number) raises ValueError saying what and where."""
    if _STORED.fullmatch(d):
        try:
            commands(d)
            return d
        except ValueError:
            pass                                        # e.g. a line after Z: SVG reads it, so it is read in full below
    out, i, cmd, cur, start, ctrl, prev = [], 0, None, (0.0, 0.0), (0.0, 0.0), None, None
    n = len(d)

    def num(flag=False):
        nonlocal i
        m = (_FLAG if flag else _NUM).match(d, i)
        if not m:
            rest = d[i:].strip()[:12]
            raise ValueError(f'{cmd} needs {_SVG_COUNT[cmd.upper()]} numbers{" (an arc flag is 0 or 1)" if flag else ""}; '
                             f'got "{rest or "the end"}"')
        i = m.end()
        return float(m.group(1))

    while True:
        i = _GAP.match(d, i).end()
        if i >= n:
            break
        if d[i].isalpha():
            if d[i].upper() not in _SVG_COUNT:
                raise ValueError(f'"{d[i]}" is not an SVG path command (M L H V C S Q T A Z, or lower case for relative)')
            cmd, i = d[i], i + 1
        elif cmd is None:
            raise ValueError(f'"{d[i:i + 8]}" before a command (start with M)')
        elif cmd in "Zz":
            raise ValueError(f'"{d[i:i + 8]}" after Z: numbers need a command')
        up, rel = cmd.upper(), cmd.islower()
        if up != "M" and not out:
            raise ValueError(f"{cmd} needs an M first")
        if up == "Z" and out[-1][0] == "Z":                     # Z Z: closed already
            continue
        if up != "M" and out[-1][0] == "Z":                     # after Z the pen is back at the start: a new subpath there
            out.append(("M", *start))
        ox, oy = cur if rel else (0.0, 0.0)
        if up == "Z":
            out.append(("Z",))
            cur, ctrl, prev = start, None, "Z"
            continue
        if up == "M":
            cur = start = (ox + num(), oy + num())
            out.append(("M", *cur))
            cmd, ctrl, prev = ("l" if rel else "L"), None, "M"      # more pairs after M are lines
            continue
        if up in "LHV":
            x = cur[0] if up == "V" else ox + num()
            y = cur[1] if up == "H" else oy + num()
            cur, ctrl = (x, y), None
            out.append(("L", *cur))
        elif up in "CS":
            if up == "C":
                c1 = (ox + num(), oy + num())
            else:
                c1 = (2 * cur[0] - ctrl[0], 2 * cur[1] - ctrl[1]) if ctrl and prev in "CS" else cur
            c2 = (ox + num(), oy + num())
            end = (ox + num(), oy + num())
            out.append(("C", *c1, *c2, *end))
            cur, ctrl = end, c2
        elif up in "QT":
            if up == "Q":
                q = (ox + num(), oy + num())
            else:
                q = (2 * cur[0] - ctrl[0], 2 * cur[1] - ctrl[1]) if ctrl and prev in "QT" else cur
            end = (ox + num(), oy + num())
            out.append(("C", cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]),
                        end[0] + 2 / 3 * (q[0] - end[0]), end[1] + 2 / 3 * (q[1] - end[1]), *end))
            cur, ctrl = end, q
        else:                                                    # A rx ry turn large sweep x y
            rx, ry, turn = abs(num()), abs(num()), num()
            large, sweep = num(flag=True), num(flag=True)
            end = (ox + num(), oy + num())
            out += _arc(cur, end, rx, ry, turn, bool(large), bool(sweep))
            cur, ctrl = end, None
        prev = up
    if not out:
        return ""
    return write(out)


def _arc(p0, p1, rx, ry, turn, large, sweep) -> list[tuple]:
    """An SVG arc (endpoint form) as cubics, one per quarter turn at most (SVG 1.1 implementation notes F.6)."""
    if p0 == p1:
        return []
    if rx == 0 or ry == 0:
        return [("L", *p1)]
    phi = math.radians(turn % 360)
    cos, sin = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = cos * dx + sin * dy, -sin * dx + cos * dy
    lam = (x1 / rx) ** 2 + (y1 / ry) ** 2
    if lam > 1:                                                  # radii too small for the two ends: scaled up, as SVG does
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num_ = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    co = math.sqrt(max(num_, 0.0) / (rx * rx * y1 * y1 + ry * ry * x1 * x1)) * (-1 if large == sweep else 1)
    cx1, cy1 = co * rx * y1 / ry, -co * ry * x1 / rx
    cx, cy = cos * cx1 - sin * cy1 + (p0[0] + p1[0]) / 2, sin * cx1 + cos * cy1 + (p0[1] + p1[1]) / 2
    ang = lambda ux, uy, vx, vy: math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)  # noqa: E731
    a0 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    da = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and da > 0:
        da -= 2 * math.pi
    elif sweep and da < 0:
        da += 2 * math.pi
    parts = max(1, math.ceil(abs(da) / (math.pi / 2) - 1e-9))
    step = da / parts
    k = 4 / 3 * math.tan(step / 4)
    pt = lambda a: (cx + rx * math.cos(a) * cos - ry * math.sin(a) * sin, cy + rx * math.cos(a) * sin + ry * math.sin(a) * cos)  # noqa: E731
    dpt = lambda a: (-rx * math.sin(a) * cos - ry * math.cos(a) * sin, -rx * math.sin(a) * sin + ry * math.cos(a) * cos)  # noqa: E731
    out = []
    for j in range(parts):
        a, b = a0 + j * step, a0 + (j + 1) * step
        (ax, ay), (bx, by), (dax, day), (dbx, dby) = pt(a), pt(b), dpt(a), dpt(b)
        if j == parts - 1:
            bx, by = p1
        out.append(("C", ax + k * dax, ay + k * day, bx - k * dbx, by - k * dby, bx, by))
    return out


def write(cmds) -> str:
    return " ".join(c[0] + ("" if len(c) == 1 else " " + " ".join(_num(v) for v in c[1:])) for c in cmds)


def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def check(d: str, where: str = "d") -> str:
    """`d` as stored (normalize), or ValueError naming `where`."""
    try:
        return normalize(d)
    except ValueError as e:
        raise ValueError(f"{where}: {e}") from None


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

def rect(w: float, h: float, r: float | tuple = 0.0, inset: float = 0.0) -> str:
    """A rectangle; `r` one radius or four (top-left, top-right, bottom-right, bottom-left). Radii too big for a side
    shrink together, as the stage's CSS box draws them."""
    x0, y0, x1, y1 = inset, inset, w - inset, h - inset
    tl, tr, br, bl = (max(0.0, c - inset) for c in (r if isinstance(r, (tuple, list)) else (r,) * 4))
    sides = [(x1 - x0, tl + tr), (y1 - y0, tr + br), (x1 - x0, br + bl), (y1 - y0, bl + tl)]
    f = min([1.0] + [max(side, 0.0) / need for side, need in sides if need > 0])
    tl, tr, br, bl = tl * f, tr * f, br * f, bl * f
    c = lambda r, ax, ay, bx, by, px, py: [("C", ax + (px - ax) * K, ay + (py - ay) * K,  # noqa: E731
                                            bx + (px - bx) * K, by + (py - by) * K, bx, by)] if r else []
    cmds = [("M", x0 + tl, y0), ("L", x1 - tr, y0), *c(tr, x1 - tr, y0, x1, y0 + tr, x1, y0),
            ("L", x1, y1 - br), *c(br, x1, y1 - br, x1 - br, y1, x1, y1), ("L", x0 + bl, y1),
            *c(bl, x0 + bl, y1, x0, y1 - bl, x0, y1), ("L", x0, y0 + tl), *c(tl, x0, y0 + tl, x0 + tl, y0, x0, y0)]
    # A line to where the pen already is (a square corner, a side all corner) is no point; nor is one back to the start.
    out = [cmds[0]] + [q for p, q in zip(cmds, cmds[1:]) if q[0] != "L" or q[-2:] != p[-2:]]
    return write(out[:-1] + [("Z",)] if out[-1][0] == "L" and out[-1][-2:] == out[0][-2:] else out + [("Z",)])


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


def shifted(d: str, shift) -> str:
    """d moved by -shift (a path placed from its own points, for_script): its keys are read the same way."""
    return write(transformed(commands(d), lambda x, y: (x - shift[0], y - shift[1]))) if shift else d


def for_script(layer) -> dict:
    """The script layer's names: `path(id, d=…)` and the primitives `star(points, outer, inner, rotation)` and
    `polygon(sides, radius, rotation)`, which give d.

    Where a path's points are: with none of x, y, w, h given, d is read as SVG reads it, in the coordinates of what
    holds the path (comp px, or the group's box): the box is fitted around d and placed there, so a line drawn through
    (360, 600) passes through (360, 600). Keys of `d` are then read the same way. With any of them given, d is in the
    path's own box (0, 0 = its top-left; w / h from d when left out) and x, y place the box's anchor."""
    def path(id=None, **values):
        shift = None
        if "d" in values:
            values["d"] = check(values["d"], f"{id or 'path'}.d")       # any SVG path data, stored as M L C Z
            cmds = commands(values["d"])
            if not {"x", "y", "w", "h", "ridePath"} & values.keys():
                cmds, (x0, y0, w, h) = fit(cmds)
                shift = (x0, y0)
                values.update(d=write(cmds), w=w, h=h, x=x0 + w * values.get("anchorX", 0.5),
                              y=y0 + h * values.get("anchorY", 0.5))
            x0, y0, x1, y1 = bounds(cmds)
            values.setdefault("w", max(x1, 1.0))
            values.setdefault("h", max(y1, 1.0))
        item = layer("path", id, **values)
        item.d_shift = shift
        return item
    return {"path": path, "star": star, "polygon": polygon}
