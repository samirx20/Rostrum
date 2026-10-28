"""What a tap does besides landing (ui_pointer): the pointer chasing a target that moves, and the reactions
("press", "ripple", "highlight", or the script's own function of the landing time)."""
from __future__ import annotations

import math

from . import ui_layout as U
from .evaluate import value_at

REACTIONS = ("press", "ripple", "highlight")
STEP = 1 / 15                                       # a moving target is followed with a key every 1/15 s
EASES = {"linear": lambda p: p, "easeIn": lambda p: p * p * p, "easeOut": lambda p: 1 - (1 - p) ** 3,
         "easeInOut": lambda p: 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2}


def reactions(then, press, ripple) -> list:
    """The reaction list of a tap: `then` (a name, ("highlight", colour), a function, or a list of them; None = press
    and ripple), minus "press" / "ripple" when `press=False` / `ripple=False`. Fails on a name it doesn't know."""
    items = ["press", "ripple"] if then is None else [then] if isinstance(then, (str, tuple)) or callable(then) else list(then)
    out = []
    for r in items:
        if callable(r):
            out.append(r)
            continue
        name, *arg = (r,) if isinstance(r, str) else r
        if name not in REACTIONS or len(arg) > (name == "highlight"):
            raise ValueError(f'tap then={r!r}: the reactions are {", ".join(REACTIONS)}, ("highlight", "#hex"), '
                             f'or a function of the landing time')
        if not ((name == "press" and press is False) or (name == "ripple" and ripple is False)):
            out.append((name, *arg))
    return out


def follow(build, pointer, p, target, share, t0, at, hold, ease):
    """Key the pointer's x / y from (p["x"], p["y"]) at t0 onto the target's spot at `at` (and on after it while `hold`).
    A target that stays still gets two eased keys; one that moves, linear keys every 1/15 s on an eased progress."""
    def spot(t):
        bx, by, bw, bh = U.box_in(build.root, target.id, p["parent"], t)
        return bx + bw * share[0], by + bh * share[1]
    tx, ty = spot(at)
    end = at + max(hold, 0.0)
    times = [t0 + (at - t0) * i / max(1, math.ceil((at - t0) / STEP)) for i in range(max(1, math.ceil((at - t0) / STEP)) + 1)]
    times += [at + (end - at) * i / math.ceil((end - at) / STEP) for i in range(1, math.ceil((end - at) / STEP) + 1)] if end > at else []
    moving = any(math.dist(spot(t), (tx, ty)) > 0.5 for t in times)
    if not moving:
        pointer.key("x", {t0: (p["x"], ease), at: tx}).key("y", {t0: (p["y"], ease), at: ty})
        return tx, ty, tx, ty, at
    shape = EASES.get(ease, EASES["easeInOut"])
    xs, ys = {}, {}
    for t in times:
        gx, gy = spot(t)
        k = shape(min(1.0, (t - t0) / (at - t0))) if at > t0 else 1.0
        xs[t], ys[t] = (p["x"] + (gx - p["x"]) * k, p["y"] + (gy - p["y"]) * k) if t <= at else (gx, gy)
    pointer.key("x", xs, ease="linear").key("y", ys, ease="linear")
    return tx, ty, xs[times[-1]], ys[times[-1]], end


def filled(node):
    """The first shape (the node itself, else the first below it) that has a fill showing."""
    if node["type"] == "shape" and node.get("filled", True) and node.get("fill"):
        return node
    for c in node.get("layers", []):
        got = filled(c)
        if got:
            return got
    return None


def highlight(build, target, colour, at):
    """The target's first filled shape (a button's `<id>_bg`) changes to `colour` over 0.15 s and stays."""
    from .script import Item
    shape = filled(target.node)
    if shape is None:
        raise ValueError(f'tap highlight: {target.id} has no filled shape to colour (an outline button, a text); '
                         f'colour what you want yourself with then=lambda t: ...')
    Item(build, shape).key("fill", {at: (value_at(shape, "fill", at), "easeOut"), at + 0.15: colour}, ease="easeOut")
