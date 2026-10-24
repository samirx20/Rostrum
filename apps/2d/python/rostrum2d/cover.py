"""Covering the frame: the one place for the maths that makes a layer's box cover what the frame shows of it, and for
where it falls short. `layer.fill_frame` (the frame where it is at one time) and `background.fit` (Cover the frame's
move: everything the frame shows over the whole piece) size and place with `scale_to_cover` and `anchor_at`; the
warning band on the canvas (screen2d/cover_band.py) and inspect_background read `edges`.

The frame rule is apps/2d/FRAME.md › The maths (frame/view.py): with s = 1 / (1 + depth) a layer at `depth` shows its
world px P + R(roll) · (q − O) / zoom**s for each output px q, P = H + s · (F − H). A layer's own box is boxes.matrix.
"""
from __future__ import annotations

import math

from .boxes import matrix
from .evaluate import _track, animated, keys_of, resolve
from .frame import view
from .sizes import own_size

BOX = frozenset(("x", "y", "scale", "scaleX", "scaleY", "rotation", "anchorX", "anchorY", "depth", "w", "h"))  # what places a box (a text's size: all)
BLEED = 24          # px past the furthest edge the frame shows: a soft edge never reaches the frame
EDGES = ("left", "top", "right", "bottom")


def turn(x: float, y: float, deg: float) -> tuple[float, float]:
    r = math.radians(deg)
    return math.cos(r) * x - math.sin(r) * y, math.sin(r) * x + math.cos(r) * y


def seen(comp: dict, shot, depth: float) -> list[tuple[float, float]]:
    """The frame's four corners in world px for a layer at `depth`, for one frame `shot` (view.Shot)."""
    w, h = float(comp.get("width", 1920)), float(comp.get("height", 1080))
    s = 1 / (1 + depth)
    z = shot.zoom ** s
    px, py = shot.hx + s * (shot.x - shot.hx), shot.hy + s * (shot.y - shot.hy)
    return [(px + dx, py + dy) for dx, dy in (turn(u * w / 2 / z, v * h / 2 / z, shot.roll)
                                              for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)))]


def scale_to_cover(need_u: float, need_v: float, w: float, h: float) -> float:
    """The scale that makes a w × h box reach `need_u`, `need_v` from its centre along its own two sides."""
    return max(need_u / (w / 2), need_v / (h / 2))


def anchor_at(cx: float, cy: float, bw: float, bh: float, ax: float, ay: float, rot: float) -> tuple[float, float]:
    """The x, y (its anchor) that puts a bw × bh box turned by `rot` with its centre at (cx, cy)."""
    dx, dy = turn((0.5 - ax) * bw, (0.5 - ay) * bh, rot)
    return cx - dx, cy - dy


def fit(comp: dict, p: dict, w: float, h: float, shots: list, bleed: float = BLEED) -> tuple[float, float, float]:
    """(scale, x, y) for a layer with values `p` and own size w × h, keeping its turn and stretch: its box covers, at its
    depth, every corner the frame shows over `shots`, with `bleed` px past the furthest."""
    rot = p["rotation"]
    pts = [turn(x, y, -rot) for shot in shots for x, y in seen(comp, shot, p["depth"])]   # in the box's own turn
    us, vs = [u for u, _ in pts], [v for _, v in pts]
    k = scale_to_cover((max(us) - min(us)) / 2 + bleed, (max(vs) - min(vs)) / 2 + bleed, w * p["scaleX"], h * p["scaleY"])
    cx, cy = turn((max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2, rot)
    x, y = anchor_at(cx, cy, w * p["scaleX"] * k, h * p["scaleY"] * k, p["anchorX"], p["anchorY"], rot)
    return k, x, y


def edges(comp: dict, layer: dict, shots: list, fps: float) -> list[dict]:
    """Where the frame sees past a layer over the piece: [{edge, short (world px, the most), from (seconds, the first
    time)}] in the order left, top, right, bottom; [] = it covers. Read with the layer's own box at each frame (its
    turn, scale and stretch then), so a turned or animated layer is judged as it shows."""
    return report(comp, layer, shots, fps)[0]


def report(comp: dict, layer: dict, shots: list, fps: float) -> tuple[list[dict], bool]:
    """(edges, whether it covers the whole frame at some moment: a backdrop, not a title the frame always sees round)."""
    worst: dict[str, list] = {}
    once, m, short, last = False, None, [], None
    p = resolve(layer, 0.0)
    moving = sorted(animated(layer) if layer["type"] == "text" else animated(layer) & BOX)    # what moves its box
    tracks = [keys_of(layer, k) for k in moving]
    for n, shot in enumerate(shots):
        now = tuple(_track(k, keys, n / fps) for k, keys in zip(moving, tracks))
        if last is None or (now, shot) != last:     # else the box and the frame are as at the frame before: same answer
            if last is None or now != last[0]:
                p.update(zip(moving, now))
                w, h = own_size(layer["type"], p)
                sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
                m = matrix(p, w, h) if w * sx > 0 and h * sy > 0 else None
            last = (now, shot)
            short = None if m is None else _short(m, seen(comp, shot, p["depth"]), w, h, sx, sy)
        if short is None:
            continue
        once = once or not short
        for edge, d in short:
            got = worst.setdefault(edge, [d, n / fps])
            got[0] = max(got[0], d)
    return [{"edge": e, "short": round(worst[e][0]), "from": round(worst[e][1], 2)} for e in EDGES if e in worst], once


def _short(m, corners, w: float, h: float, sx: float, sy: float) -> list[tuple[str, float]]:
    """[(edge, px)]: how far past each of the box's edges the frame's corners reach (more than half a px)."""
    own = [view.undo(m, x, y) for x, y in corners]
    us, vs = [u for u, _ in own], [v for _, v in own]
    return [(e, d) for e, d in zip(EDGES, (-min(us) * sx, -min(vs) * sy, (max(us) - w) * sx, (max(vs) - h) * sy)) if d > 0.5]


def words(edge: dict) -> str:
    """'shows past the right edge from 3.2 s' ('… from the start' when it does at once)."""
    when = f"{edge['from']:.1f} s" if edge["from"] >= 0.05 else "the start"
    return f"shows past the {edge['edge']} edge from {when}"
