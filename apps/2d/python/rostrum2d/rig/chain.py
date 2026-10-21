"""Long IK chains (RIG.md › Long chains): an `ik` whose `chain` is more than 2 bones (a tail, a spine, a tentacle,
an arm with a hand bone) is solved here, per frame, by FABRIK (forward and backward reaching), and sent to the engine
as per-frame `rotation` keys on its bones (linear, exact at every frame), as an expression is (exprbake.py). The
engine never sees the ik itself; two-bone chains stay the engine's (ik.rs).

Per frame: the bones are posed by FK (fk.py, the engine's rule), the chain's joints are moved by FABRIK so the last
tip reaches the (held) target, the turns found are blended with FK by `mix` and added to each bone's own rotation.
A chain that starts straight curls the way `bend` says. A pinned target holds as the two-bone one does.
"""
from __future__ import annotations

import math

from rostrum_core.keys import keys_of, track_value

from . import fk

PY_ONLY = {"ik": {"chain"}}
TRIES, CLOSE = 24, 0.01                     # FABRIK passes at most; stop when the tip is this close, px


def is_long(item: dict) -> bool:
    return item.get("type") == "ik" and int(item.get("chain", 2)) > 2


def bones_of(rig: dict, ik: dict) -> list[str]:
    """The chain's bones, top first: the lower bone and its parents, `chain` in all (fewer when the rig runs out)."""
    parent = {b["id"]: b.get("parent", "") for b in rig.get("bones", [])}
    out, cur = [], ik["bone"]
    while cur and len(out) < int(ik.get("chain", 2)):
        out.insert(0, cur)
        cur = parent.get(cur, "")
    return out


def _value(item, prop, t, default):
    keys = keys_of(item, prop)
    return float(track_value(keys, t)) if keys else float(item.get(prop, default))


def pin_start(keys: list, t: float) -> float:
    """The start of the stretch up to t where pin ≥ 0.5 (−inf: on all along); the engine's rule (ik.rs)."""
    on = lambda s: float(track_value(keys, s)) >= 0.5  # noqa: E731
    hi = t
    for edge in sorted((k["t"] for k in keys if k["t"] < t), reverse=True):
        for i in range(1, 65):
            s = hi - (hi - edge) * i / 64
            if not on(s):
                off, lit = s, hi - (hi - edge) * (i - 1) / 64
                for _ in range(60):
                    m = 0.5 * (off + lit)
                    off, lit = (off, m) if on(m) else (m, lit)
                return next((k["t"] for k in keys if abs(k["t"] - lit) < 1e-6 and on(k["t"])), lit)
        hi = edge
    return -math.inf


def target(ik: dict, t: float) -> tuple[float, float]:
    """The target at t, held from the moment the pin turned on while it is on."""
    pins = keys_of(ik, "pin")
    if _value(ik, "pin", t, 0.0) >= 0.5:
        t = pin_start(pins, t) if pins else -math.inf
    return _value(ik, "targetX", t, 0.0), _value(ik, "targetY", t, 0.0)


def fabrik(points: list, goal, clockwise: bool) -> list:
    """Joint positions (base first) moved so the last reaches `goal`, lengths kept, base fixed."""
    pts = [list(p) for p in points]
    lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    side = 1.0 if clockwise else -1.0
    for i in range(1, len(pts) - 1):           # a straight chain has no way to fold: curl it a little, `bend`'s way
        a, b = _heading(pts[i - 1], pts[i]), _heading(pts[i], pts[i + 1])
        if abs(_wrap(b - a)) < math.radians(2):
            n = a + side * math.pi / 2
            pts[i][0] += 0.02 * lens[i - 1] * math.cos(n)
            pts[i][1] += 0.02 * lens[i - 1] * math.sin(n)
    base = list(pts[0])
    if math.dist(base, goal) >= sum(lens):     # out of reach: straight at it
        h = _heading(base, goal)
        for i, l in enumerate(lens):
            pts[i + 1] = [pts[i][0] + l * math.cos(h), pts[i][1] + l * math.sin(h)]
        return pts
    for _ in range(TRIES):
        pts[-1] = list(goal)
        for i in range(len(pts) - 2, -1, -1):
            pts[i] = _toward(pts[i + 1], pts[i], lens[i])
        pts[0] = list(base)
        for i in range(len(pts) - 1):
            pts[i + 1] = _toward(pts[i], pts[i + 1], lens[i])
        if math.dist(pts[-1], goal) < CLOSE:
            break
    return pts


def _toward(fixed, free, length):
    d = math.dist(fixed, free) or 1e-9
    return [fixed[0] + (free[0] - fixed[0]) * length / d, fixed[1] + (free[1] - fixed[1]) * length / d]


def _heading(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def turns(rig: dict, ik: dict, t: float, baked: dict, extra: dict | None = None) -> dict[str, float]:
    """{bone id: degrees added to its rotation} that make the chain reach its target at t (mix applied), on top of
    `extra` (the turns other chains found this frame)."""
    if ik.get("mode", "ik") != "ik":
        return {}
    chain = bones_of(rig, ik)
    posed = fk.pose(rig, t, baked, extra)
    joints = [fk.pivot(posed[b]) for b in chain] + [fk.tip(posed[chain[-1]])]
    solved = fabrik(joints, target(ik, t), ik.get("bend", "clockwise") == "clockwise")
    mix = min(max(_value(ik, "mix", t, 1.0), 0.0), 1.0)
    out, before = {}, 0.0
    for i, b in enumerate(chain):
        world = mix * _wrap(_heading(solved[i], solved[i + 1]) - _heading(joints[i], joints[i + 1]))
        out[b] = math.degrees(world - before)     # a child's turn adds to its parent's: give only the difference
        before = world
    return out


def solve(rig: dict, t: float, baked: dict) -> dict[str, float]:
    """Every long chain of the rig at t, upper chains first (a lower chain poses on top of them)."""
    bones = {b["id"]: b for b in rig.get("bones", [])}
    chains = sorted((k for k in rig.get("iks", []) if is_long(k)), key=lambda k: fk.depth(bones, bones_of(rig, k)[0]))
    extra: dict[str, float] = {}
    for k in chains:
        for b, d in turns(rig, k, t, baked, extra).items():
            extra[b] = extra.get(b, 0.0) + d
    return extra


def _rigs(node: dict):
    for child in node.get("layers", []):
        if child.get("type") == "rig":
            yield child
        yield from _rigs(child)


def bake(comp: dict, fps: float, baked: dict) -> dict[str, dict[str, list]]:
    """{bone id: {"rotation": per-frame keys}} for every bone in a long chain of the composition."""
    out: dict[str, dict[str, list]] = {}
    count = int(round(comp.get("duration", 10.0) * fps)) + 1
    for rig in _rigs(comp):
        long = [k for k in rig.get("iks", []) if is_long(k)]
        if not long:
            continue
        bones = {b["id"]: b for b in rig["bones"]}
        rows = {b: [] for k in long for b in bones_of(rig, k)}
        for f in range(count):
            t = f / fps
            extra = solve(rig, t, baked)
            for b, keys in rows.items():
                keys.append({"t": round(t, 6), "v": fk.field(bones[b], "rotation", t, baked, 0.0) + extra.get(b, 0.0),
                             "ease": "linear"})
        out.update({b: {"rotation": keys} for b, keys in rows.items()})
    return out
