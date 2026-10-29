"""passes_through:<a>~<b> (round 7 of the 3D gaps: Ink's ball rolled through a cone and a box, a ring sank into its plinth):
two placed things not built as one (grouped, attached, stuck) whose real forms sink into each other deeper than DEEP_M on a
checked frame; an entry of the shot's one fault list (faults.py). A sphere, box, cylinder, cone, capsule or torus is its exact
form (surface points and a signed distance), not its box: the depth is how far the deepest surface point of either lies in the
other, so a ball resting on a box or a ring standing on a plinth stays silent. A thing wholly inside a see-through one
(transmission over 0: liquid in a bottle, an ice cube in a glass) is meant to be there and is not judged (gaps7 Drop: both
agents had to keep "bottle~juice"). Other shapes (an editable mesh, a clay, an
import) are not checked; the ground, floor, walls and backdrop are framing (sinking into a floor is shot_faults' sinking).
look_motion's passes_through finding measures with `depth` too (mcp/motion_found.py).
"""
from __future__ import annotations

import math
import re

from rostrum_core.mcp import faults as F

from . import aim

DEEP_M = 0.01            # sunk deeper than this: a pass-through (touching, ≤ 1 cm, is resting on it)
CLEAR_M = 0.005          # the fix moves it this much past touching
STEP_S = 0.25            # frames checked over a whole shot: one every this many seconds
BIG_M = 3.0              # this long or more: a floor, wall or backdrop
_BACK = re.compile(r"ground|floor|wall|sky|backdrop|cyc|room|stage", re.I)
FORMS = ("sphere", "box", "cylinder", "cone", "capsule", "torus")
_AXES = ("x", "y", "z")


def _profile(v: dict) -> list[tuple[float, float]]:
    """(distance from the Y axis, height) points along a round form's outline, turned about Y they cover its surface."""
    s, r, h = v["shape"], float(v.get("radius", 0.5)), float(v.get("height", 1.0))
    if s == "sphere":
        return [(r * math.cos(a), r * math.sin(a)) for a in (math.pi * (k / 8 - 0.5) for k in range(9))]
    if s == "torus":
        t = float(v.get("tube", 0.1))
        return [(r + t * math.cos(a), t * math.sin(a)) for a in (2 * math.pi * k / 10 for k in range(10))]
    if s == "capsule":
        m = max(0.0, h / 2 - r)
        return [(r * math.cos(a), (m if a > 0 else -m) + r * math.sin(a)) for a in (math.pi * (k / 8 - 0.5) for k in range(9))]
    top = 0.0 if s == "cone" else r
    line = [(0.0, -h / 2), (r, -h / 2), (top, h / 2), (0.0, h / 2)]
    return [(a[0] + (b[0] - a[0]) * k / 4, a[1] + (b[1] - a[1]) * k / 4) for a, b in zip(line, line[1:]) for k in range(5)]


def surface(v: dict) -> list[list[float]]:
    """Points on a form's surface in its own space (centred on its origin, up +Y; item_bounds._shape_box)."""
    if v["shape"] == "box":
        h = [float(v[k]) / 2 for k in ("width", "height", "depth")]       # a 5 × 5 grid on each face
        return [[h[k] * (side if k == ax else (i if k == (ax + 1) % 3 else j) / 2 - 1) for k in range(3)]
                for ax in range(3) for side in (-1, 1) for i in range(5) for j in range(5)]
    n = 16
    return [[rho * math.cos(2 * math.pi * k / n), y, rho * math.sin(2 * math.pi * k / n)]
            for rho, y in _profile(v) for k in range(n if rho > 1e-9 else 1)]


def sdf(v: dict, p) -> float:
    """Signed distance from p (own space) to the form's surface: negative inside."""
    s, x, y, z = v["shape"], *p
    if s == "box":
        q = [abs(c) - float(v[k]) / 2 for c, k in zip(p, ("width", "height", "depth"))]
        return math.hypot(*(max(c, 0.0) for c in q)) + min(max(q), 0.0)
    r, h, rho = float(v.get("radius", 0.5)), float(v.get("height", 1.0)), math.hypot(x, z)
    if s == "sphere":
        return math.hypot(x, y, z) - r
    if s == "torus":
        return math.hypot(rho - r, y) - float(v.get("tube", 0.1))
    if s == "capsule":
        m = max(0.0, h / 2 - r)
        return math.hypot(rho, y - min(max(y, -m), m)) - r
    if s == "cylinder":
        q = (rho - r, abs(y) - h / 2)
        return math.hypot(max(q[0], 0.0), max(q[1], 0.0)) + min(max(q), 0.0)
    # cone: the triangle (0,-h/2) (r,-h/2) (0,h/2) turned about Y
    edges = [((0.0, -h / 2), (r, -h / 2)), ((r, -h / 2), (0.0, h / 2))]
    dist = min(_seg(rho, y, a, b) for a, b in edges)
    inside = y >= -h / 2 and rho * h + y * r <= r * h / 2
    return -dist if inside else dist


def _seg(x, y, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = min(max(((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy), 0.0), 1.0)
    return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)


def _scale(m) -> float:
    return min(math.sqrt(sum(row[k] ** 2 for row in m[0])) for k in range(3))


class Placed:
    """One form at one frame: its values, world transform, world surface points."""

    def __init__(self, v: dict, world):
        self.v, self.m, self.inv, self.s = v, world, aim.invert(world), _scale(world)
        self.pts = [aim.point(world, p) for p in surface(v)]
        self.lo = [min(p[k] for p in self.pts) for k in range(3)]
        self.hi = [max(p[k] for p in self.pts) for k in range(3)]

    def dist(self, p) -> float:
        return sdf(self.v, aim.point(self.inv, p)) * self.s

    def normal(self, p) -> list[float]:
        e, d0 = 1e-4, self.dist(p)
        g = [(self.dist([p[i] + (e if i == k else 0.0) for i in range(3)]) - d0) / e for k in range(3)]
        n = math.hypot(*g) or 1.0
        return [c / n for c in g]


def depth(a: Placed, b: Placed):
    """(how deep a and b sink into each other in m, the deepest point, which one it is on: 'a' | 'b'); depth 0 when apart."""
    if any(a.hi[k] < b.lo[k] or b.hi[k] < a.lo[k] for k in range(3)):
        return 0.0, None, None
    best = (0.0, None, None)
    for pts, other, side in ((a.pts, b, "a"), (b.pts, a, "b")):
        for p in pts:
            if (d := -other.dist(p)) > best[0]:
                best = (d, p, side)
    return best


def placed(fr, id_: str, f: int) -> Placed | None:
    item = fr.items[id_]
    if item["type"] != "mesh" or item.get("shape") not in FORMS:
        return None
    return Placed(fr.values(id_, f), fr.world(id_, f))


def contact_faults(track, info: dict, check: list[int]) -> list[dict]:
    from .faults import when
    fr, s0 = track.fr, info["start"]
    fs = check if len(check) == 1 else sorted(set(range(s0, info["end"] + 1, max(1, round(info["fps"] * STEP_S)))) | set(check))
    ids = []
    for i in track.ids():
        it = fr.items[i]
        if i in track.skipped or it["type"] != "mesh" or it.get("shape") not in FORMS or it.get("simulate") == "cloth" \
                or _BACK.search(i) or _BACK.search(it.get("name") or ""):
            continue
        p = placed(fr, i, fs[0])
        if p and max(p.hi[k] - p.lo[k] for k in range(3)) < BIG_M:
            ids.append(i)
    forms = {f: {i: placed(fr, i, f) for i in ids if track.shown(i, f)} for f in fs}
    worst: dict[tuple, tuple] = {}
    for n, a in enumerate(ids):
        for b in ids[n + 1:]:
            if _built_as_one(fr, a, b):
                continue
            for f in fs:
                if a in forms[f] and b in forms[f] and not _seen_inside(track.data, fr, forms[f], a, b):
                    d = depth(forms[f][a], forms[f][b])[0]
                    if d > DEEP_M and d > worst.get((a, b), (0.0,))[0]:
                        worst[(a, b)] = (d, f)
    out = []
    for (a, b), (d, f) in worst.items():
        x, y = sorted((a, b))
        mover, other, deep, fix = _fix(fr, info, a, b, forms[f], f)
        out.append(F.fault(f"passes_through:{x}~{y}", f"{mover} passes through {other}: {max(d, deep) * 100:.1f} cm deep at "
                           f"{(f - s0) / info['fps']:.1f} s", fix, when(info, f)))
    return out


def _seen_inside(data: dict, fr, forms: dict, a: str, b: str) -> bool:
    """One of a, b wholly inside the other, and the outer one see-through (its material's transmission over 0)."""
    clear = {m["id"] for m in data.get("materials", []) if float(m.get("transmission", 0) or 0) > 0}
    for inner, outer in ((a, b), (b, a)):
        if fr.items[outer].get("material") in clear and all(forms[outer].dist(p) <= 0 for p in forms[inner].pts):
            return True
    return False


def _built_as_one(fr, a: str, b: str) -> bool:
    """Grouped (same parent: faults._linked), one inside the other, or one attached or stuck to the other."""
    pa, pb, ia, ib = fr.parent.get(a), fr.parent.get(b), fr.items[a], fr.items[b]
    return ((pa is not None and pa == pb) or pa == b or pb == a or ia.get("follow") == b or ib.get("follow") == a
            or ia.get("stick") == b or ib.get("stick") == a)


def clear(mover: Placed, other: Placed, n) -> float:
    """How far `mover` has to move along n until no point of either lies inside the other (m)."""
    def apart(s):
        return all(other.dist([p[k] + s * n[k] for k in range(3)]) >= 0 for p in mover.pts) and             all(mover.dist([q[k] - s * n[k] for k in range(3)]) >= 0 for q in other.pts)
    span = sum(max(x.hi[k] - x.lo[k] for k in range(3)) for x in (mover, other))
    step = max(span / 100, 0.002)
    s = next((s for s in (i * step for i in range(101)) if apart(s)), span)
    lo = max(s - step, 0.0)
    for _ in range(6):                                   # the exact distance between the last step in and the first out
        lo, s = (lo, (lo + s) / 2) if apart((lo + s) / 2) else ((lo + s) / 2, s)
    return s


def _fix(fr, info, a, b, forms, f) -> tuple[str, str, float, str]:
    """(the one to move, the other, how far they have to part, the fix): the keyed one, else the smaller, moves the shortest
    way out (a moving one: across its path, not along it)."""
    def keyed(i):
        return [k for k in fr.items[i].get("keys", []) if k.get("prop") in _AXES and isinstance(k.get("t"), (int, float))]
    size = lambda i: max(forms[i].hi[k] - forms[i].lo[k] for k in range(3))        # noqa: E731
    mover = max((a, b), key=lambda i: (bool(keyed(i)), -size(i)))
    other = b if mover == a else a
    here, f1 = fr.world(mover, f)[1], min(f + 2, info["end"])
    go = [x - y for x, y in zip(fr.world(mover, f1 if f1 != f else max(f - 2, info["start"]))[1], here)]
    along = max(range(3), key=lambda i: abs(go[i])) if math.hypot(*go) > 1e-4 else None
    ways = [(clear(forms[mover], forms[other], w), w) for w in
            ([(1.0 if k == ax else 0.0) * sign for k in range(3)] for ax in range(3) for sign in (1, -1))]
    least = min(m for m, _ in ways)                      # about as short across its path beats along it, then up beats down
    m, n = min(((m, w) for m, w in ways if m <= least * 1.25 + 0.005), key=lambda x: (abs(x[1][along]) if along is not None
                                                                                       else 0, x[1][1] < 0, x[0]))
    k = max(range(3), key=lambda i: abs(n[i]))
    t = (f - info["start"]) / info["fps"]
    move = f"move {mover} {m + CLEAR_M:.2f} m along {'+' if n[k] > 0 else '-'}{_AXES[k]}"
    ks = [x for x in keyed(mover) if x.get("prop") == _AXES[k]]
    if ks:
        near = min(ks, key=lambda x: abs(float(x["t"]) - t))
        move += f" around {t:.1f} s (its {near['prop']} key at {float(near['t']):.2f} s, or add one there)"
    elif keyed(mover):
        move += f" around {t:.1f} s (add a {_AXES[k]} key there; its path goes through {other})"
    else:
        move += f" (it sinks into {other} at {t:.1f} s)"
    tail = f", or {mover}.place_on(\"{other}\")" if _AXES[k] == "y" and n[k] > 0 else ""
    return mover, other, least, (f"{move}{tail}; if they are one thing, group them (group(...)) or attach_to={other}; if passing "
                             "through is meant, keep it")
