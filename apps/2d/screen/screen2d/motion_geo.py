"""Where a moving layer (or the camera) travels, as the canvas shows it: the motion path's maths (motion_path.py draws
nothing itself; this module has no Qt).

Two halves, so a playhead move costs little: `track` reads the document once per change and selection (the layer's own
x / y per frame between its first and last position key, in its parent's px; the camera's look point in composition px),
and `mapping` gives, at the playhead, the matrix from those px to the canvas (through the layer's groups and the camera
showing then, mcp/geometry.py and camera/view.py: the same maths as the engine). A key's spatial handles are offsets
from its value (`out`, `in`; key.path_handles); a key without one shows the default third of the way to its neighbour.
Positions come from rostrum2d.evaluate.value_at, so the path follows the one evaluation rule.
"""
from __future__ import annotations

from rostrum2d.frame import view as camera
from rostrum2d.evaluate import value_at
from rostrum2d.mcp.geometry import flatten
from rostrum_core.keys.evaluate import keys_of

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


def track(owner: dict, fps: float) -> dict | None:
    """The layer's travel in its own parent's px: {points, ticks, keys}; None without two position keys."""
    times = _keys(owner)
    if len(times) < 2:
        return None
    t0, t1 = next(iter(times)), next(reversed(times))
    n = max(1, round((t1 - t0) * fps))
    steps = min(n * FRAME_STEPS, MOST_POINTS)
    pos = lambda t: (float(value_at(owner, "x", t)), float(value_at(owner, "y", t)))   # noqa: E731
    points = [pos(t0 + (t1 - t0) * i / steps) for i in range(steps + 1)]
    ticks = [pos(t0 + (t1 - t0) * i / n) for i in range(n + 1)]
    at = list(times.items())
    keys = []
    for i, (t, ks) in enumerate(at):
        x, y = pos(t)
        prev = pos(at[i - 1][0]) if i else None
        nxt = pos(at[i + 1][0]) if i + 1 < len(at) else None
        stored = any(isinstance(k.get(s), (int, float)) for k in ks.values() for s in ("out", "in"))
        keys.append({"t": t, "x": x, "y": y, "ids": [k["id"] for k in ks.values()], "stored": stored,
                     "out": None if nxt is None else [_handle(ks, "x", "out", x, nxt[0]), _handle(ks, "y", "out", y, nxt[1])],
                     "in": None if prev is None else [_handle(ks, "x", "in", x, prev[0]), _handle(ks, "y", "in", y, prev[1])]})
    return {"points": points, "ticks": ticks, "keys": keys}


def camera_keys(cam: dict) -> list[float]:
    """Every time the camera has a key on where it looks, how close or how turned (its frame is outlined at each)."""
    return sorted({round(float(k["t"]), 6) for p in CAM_PROPS for k in keys_of(cam, p) if isinstance(k.get("t"), (int, float))})


def mapping(comp: dict, owner: dict, t: float):
    """The matrix from the owner's travel px to the canvas at the playhead t: a layer through its groups (or, at the
    top, the camera showing then, by its depth); the camera's look point through the view at depth 0."""
    cam = camera.shot(comp, t)
    if owner["type"] == "camera":
        return camera.layer_matrix(comp, cam, {"depth": 0.0})
    every = {e["id"]: e for e in flatten(comp, t)}
    e = every.get(owner["id"])
    if e is None:
        return camera.ID
    return every[e["within"][-1]]["matrix"] if e["within"] else camera.layer_matrix(comp, cam, e["props"])


def frame_at(comp: dict, cam: dict, t: float, now) -> list[list[float]]:
    """The camera's frame at time t (the composition rectangle it shows then) as the canvas shows it now (`now`)."""
    w, h = comp.get("width", 1920), comp.get("height", 1080)
    m = camera.layer_matrix(comp, camera.shot(comp, t), {"depth": 0.0})
    return [apply(now, *camera.undo(m, x, y)) for x, y in ((0, 0), (w, 0), (w, h), (0, h))]


def on_canvas(tr: dict, m) -> dict:
    """The travel mapped to the canvas: points, ticks and keys (with handle ends) in composition px as seen."""
    keys = []
    for k in tr["keys"]:
        row = {"t": k["t"], "ids": k["ids"], "stored": k["stored"], "own": [k["x"], k["y"]], "pos": apply(m, k["x"], k["y"])}
        for side in ("out", "in"):
            d = k[side]
            row[side] = None if d is None else apply(m, k["x"] + d[0], k["y"] + d[1])
            row[side + "Own"] = d
        keys.append(row)
    return {"points": [apply(m, *p) for p in tr["points"]], "ticks": [apply(m, *p) for p in tr["ticks"]], "keys": keys}
