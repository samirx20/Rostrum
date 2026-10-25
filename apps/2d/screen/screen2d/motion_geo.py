"""Where a moving layer (or the frame) travels, as the canvas shows it: the motion path's maths (motion_path.py draws
nothing itself; this module has no Qt).

Two halves, so a playhead move costs little: `track` reads the document once per change and selection (the layer's own
x / y per frame between its first and last position key, in its parent's px; the frame's centre in world px), and
`mapping` gives, at the playhead, the matrix from those px to the canvas (world px: through the layer's groups and the
world view's matrix for its depth, frame/view.py: the same maths as the engine). A stretch after a key with the `hold`
ease is a jump (a cut): a straight line with no ticks. A key's spatial handles are offsets from its value (`out`, `in`;
key.path_handles); a key without one shows the default third of the way to its neighbour. Positions come from
rostrum2d.evaluate.value_at, so the path follows the one evaluation rule.
"""
from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache

from rostrum2d.evaluate import value_at
from rostrum2d.frame import TYPE as FRAME, view as fview
from rostrum2d.mcp.geometry import _invert, _mul, flatten
from rostrum_core.keys.after import after_of
from rostrum_core.keys.easing import ease
from rostrum_core.keys.evaluate import keys_of, track_value
from rostrum_core.keys.spatial import between

FRAME_STEPS = 4                 # path points per frame (a fast curve stays smooth); ticks stay one per frame
MOST_POINTS = 4000              # a very long move is sampled more thinly, never more than this
CAM_PROPS = ("x", "y", "zoom", "rotation")


def apply(m, x: float, y: float) -> list[float]:
    return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]


def back(m, dx: float, dy: float) -> tuple[float, float]:
    """A canvas offset back through the matrix's linear part (the layer's own px)."""
    a, b, c, d = m[:4]
    det = a * d - b * c or 1.0
    return (d * dx - c * dy) / det, (-b * dx + a * dy) / det


def _keys(owner: dict) -> dict[float, dict]:
    """{t: {"x": key, "y": key}} for every time either position field has a key (composition seconds)."""
    out: dict[float, dict] = {}
    for prop in ("x", "y"):
        for k in keys_of(owner, prop):
            if isinstance(k.get("t"), (int, float)):
                out.setdefault(round(float(k["t"]), 6), {})[prop] = k
    return dict(sorted(out.items()))


def _handle(at: dict, prop: str, side: str, here: float, there: float | None) -> float:
    k = at.get(prop)
    if k is not None and isinstance(k.get(side), (int, float)):
        return float(k[side])
    return 0.0 if there is None else (there - here) / 3


_NOT_EASE = {"id", "type", "prop", "t", "v", "out", "in"}


@lru_cache(maxsize=1 << 16)
def _eased(sig: tuple, u: float) -> float:
    return ease(dict(sig), u)


def _field(owner: dict, prop: str):
    """t -> the field's value, by the one evaluation rule (rostrum_core.keys: ease, then `between`), with its keys
    sorted once and each ease's progress remembered: a drag moves values, never eases, so the curve solve is reused."""
    keys = keys_of(owner, prop)
    if not keys:
        v = float(value_at(owner, prop, 0.0))
        return lambda t: v
    sigs = [tuple(sorted((f, x) for f, x in k.items() if f not in _NOT_EASE)) for k in keys]
    try:
        hash(tuple(sigs))
        plain = after_of(keys) == "stay" and all(isinstance(k.get(f), (int, float)) for k in keys for f in ("t", "v"))
    except TypeError:
        plain = False
    if not plain:                                       # repeats, marker keys, an unusual ease: the evaluator as it is
        return lambda t: float(track_value(keys, t))
    times = [float(k["t"]) for k in keys]

    def at(t: float) -> float:
        i = bisect_right(times, t)
        if i == 0 or i == len(keys):
            return float(keys[0 if i == 0 else -1]["v"])
        k0, k1 = keys[i - 1], keys[i]
        return float(between(k0, k1, _eased(sigs[i - 1], (t - times[i - 1]) / (times[i] - times[i - 1]))))
    return at


def _position(owner: dict):
    fx, fy = _field(owner, "x"), _field(owner, "y")
    return lambda t: (fx(t), fy(t))


def _jump(at: dict) -> bool:
    """A stretch starting at these keys is a jump (a cut): every position key there holds (the `hold` ease)."""
    return all(k.get("ease") == "hold" for k in at.values())


def track(owner: dict, fps: float) -> dict | None:
    """The layer's travel in its own parent's px: {lines, cuts, ticks, keys}; None without two position keys. `lines`
    are the travelled stretches (one polyline per run between jumps), `cuts` the jumps ([from, to]: nothing travels
    there, so no ticks), `ticks` a point per frame on the travelled stretches."""
    times = _keys(owner)
    if len(times) < 2:
        return None
    t0, t1 = next(iter(times)), next(reversed(times))
    pos = _position(owner)
    at = list(times.items())
    lines, cuts, ticks, run = [], [], [], []
    for (ta, ka), (tb, _) in zip(at, at[1:]):
        if _jump(ka):
            if len(run) > 1:
                lines.append(run)
            run = []
            cuts.append([pos(ta), pos(tb)])
            continue
        n = max(1, round((tb - ta) * fps))
        per = max(1, min(FRAME_STEPS, round(MOST_POINTS * (tb - ta) / (t1 - t0) / n)))   # points per frame
        pts = [pos(ta + (tb - ta) * i / (n * per)) for i in range(n * per + 1)]
        run += pts[1:] if run else pts
        ticks += pts[::per][1:] if ticks else pts[::per]                # a tick per frame: every per-th point
    if len(run) > 1:
        lines.append(run)
    keys = []
    for i, (t, ks) in enumerate(at):
        x, y = pos(t)
        prev = pos(at[i - 1][0]) if i and not _jump(at[i - 1][1]) else None        # no handles across a jump
        nxt = pos(at[i + 1][0]) if i + 1 < len(at) and not _jump(ks) else None
        stored = any(isinstance(k.get(s), (int, float)) for k in ks.values() for s in ("out", "in"))
        keys.append({"t": t, "x": x, "y": y, "ids": [k["id"] for k in ks.values()], "stored": stored,
                     "out": None if nxt is None else [_handle(ks, "x", "out", x, nxt[0]), _handle(ks, "y", "out", y, nxt[1])],
                     "in": None if prev is None else [_handle(ks, "x", "in", x, prev[0]), _handle(ks, "y", "in", y, prev[1])]})
    return {"lines": lines, "cuts": cuts, "ticks": ticks, "keys": keys}


def frame_keys(cam: dict) -> list[float]:
    """Every time the frame has a key on where it is, how close or how turned (it is outlined faintly at each)."""
    return sorted({round(float(k["t"]), 6) for p in CAM_PROPS for k in keys_of(cam, p) if isinstance(k.get("t"), (int, float))})


def mapping(comp: dict, owner: dict, t: float):
    """The matrix from the owner's travel px to the canvas (world px) at the playhead t: a layer through its groups (or,
    at the top, the world view's matrix for its depth, frame/view.py); the frame's own travel is already in world px."""
    if owner["type"] == FRAME:
        return fview.ID
    cam = fview.shot(comp, t)
    every = {e["id"]: e for e in flatten(comp, t, only=_chain(comp.get("layers", []), owner["id"]))}
    e = every.get(owner["id"])
    if e is None:
        return fview.ID
    if not e["within"]:
        return fview.world_matrix(comp, cam, e["props"])
    top = every[e["within"][0]]["props"]            # a group's matrix is the export's: swap the top's export matrix for its world one
    swap = _mul(fview.world_matrix(comp, cam, top), _invert(fview.layer_matrix(comp, cam, top)) or fview.ID)
    return _mul(swap, every[e["within"][-1]]["matrix"])


def _chain(layers: list, lid: str) -> set:
    """The layer and the groups it sits in: all the mapping reads (a busy scene's other layers are never worked out)."""
    for layer in layers:
        if layer["id"] == lid:
            return {lid}
        if inner := _chain(layer.get("layers", []), lid):
            return inner | {layer["id"]}
    return set()


def frame_at(comp: dict, t: float) -> list[list[float]]:
    """The frame's quad at time t in world px (the output rectangle carried back through the frame then), turned and
    zoomed: the canvas draws it as it draws the world."""
    w, h = fview.centre(comp)
    m = fview.layer_matrix(comp, fview.shot(comp, t), {"depth": 0.0})
    return [list(fview.undo(m, x, y)) for x, y in ((0, 0), (2 * w, 0), (2 * w, 2 * h), (0, 2 * h))]


def _flat(m, pts) -> list[float]:
    """Points mapped to the canvas as one flat run x0, y0, x1, y1 …: the canvas gets ~800 numbers per path, not ~800
    lists of two (each a list QML is handed on every step of a drag: ~0.5 ms a path)."""
    a, b, c, d, e, f = m
    out = []
    for x, y in pts:
        out += (a * x + c * y + e, b * x + d * y + f)
    return out


def on_canvas(tr: dict, m) -> dict:
    """The travel mapped to the canvas, in world px: lines, cuts and ticks as flat runs of x, y (_flat), and keys (with
    handle ends) as points."""
    keys = []
    for k in tr["keys"]:
        row = {"t": k["t"], "ids": k["ids"], "stored": k["stored"], "own": [k["x"], k["y"]], "pos": apply(m, k["x"], k["y"])}
        for side in ("out", "in"):
            d = k[side]
            row[side] = None if d is None else apply(m, k["x"] + d[0], k["y"] + d[1])
            row[side + "Own"] = d
        keys.append(row)
    return {"lines": [_flat(m, line) for line in tr["lines"]], "cuts": [_flat(m, cut) for cut in tr["cuts"]],
            "ticks": _flat(m, tr["ticks"]), "keys": keys}
