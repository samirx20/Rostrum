"""The plain maths behind the agent paint tools (paint_look.py), no engine: canvas pixels ↔ uv, finding a spot of the
canvas in a texel picture (texels.py: which item and uv each screen pixel shows), what is painted where the shot
looks, the coverage hatch, and a stroke's report line.

Canvas pixels: x right, y down, 0..size on a square paint picture of side `size` (paintSize). uv: u right, v up,
0..1. x = u × size, y = (1 − v) × size: the same rule as look_at's `uv` and clay_paint.Surface.canvas_px.
"""
from __future__ import annotations

import numpy as np

HATCH = (255, 140, 0)                   # seen but unpainted: the screen's coverage tint colour
PAINTED_AT = 0.5                        # a canvas alpha at or over this counts as painted (coverage.PAINTED)


def px_of(uv, size: int) -> list[float]:
    """Canvas pixel [x, y] of a uv [u, v]."""
    return [float(uv[0]) * size, (1.0 - float(uv[1])) * size]


def uv_of(px, size: int) -> list[float]:
    """uv [u, v] of a canvas pixel [x, y]."""
    return [float(px[0]) / size, 1.0 - float(px[1]) / size]


def sample(canvas: np.ndarray, uv: np.ndarray) -> np.ndarray:
    """The canvas (S, S[, C]) at each uv (..., 2), nearest pixel; NaN uv (no surface coordinates there) gives 0."""
    size = canvas.shape[0]
    ok = np.isfinite(uv).all(axis=-1)
    u = np.where(ok, uv[..., 0], 0.0)
    v = np.where(ok, uv[..., 1], 1.0)
    xs = np.clip((u * size).astype(np.int64), 0, size - 1)
    ys = np.clip(((1.0 - v) * size).astype(np.int64), 0, size - 1)
    out = canvas[ys, xs]
    return np.where(ok[..., None] if out.ndim > ok.ndim else ok, out, 0)


def footprint(uv: np.ndarray, x: int, y: int, size: int) -> float:
    """How many canvas px one screen pixel spans at screen (x, y): the uv step to its right / lower neighbour."""
    h, w = uv.shape[:2]
    here = uv[y, x]
    steps = [np.abs(uv[y, min(x + 1, w - 1)] - here), np.abs(uv[min(y + 1, h - 1), x] - here)]
    found = [float(np.max(s)) * size for s in steps if np.isfinite(s).all()]
    return max(found) if found else 1.0


def nearest_seen(uv: np.ndarray, shows: np.ndarray, want, size: int) -> dict | None:
    """Where the shot shows canvas spot `want` (uv) of one item: {pixel [x, y], offPx (canvas px from the spot to what
    that pixel shows), seen (offPx within a screen pixel's span there)}, or None when the item isn't in the picture."""
    ys, xs = np.nonzero(shows & np.isfinite(uv).all(axis=-1))
    if not len(xs):
        return None
    d = np.hypot((uv[ys, xs, 0] - want[0]) * size, (uv[ys, xs, 1] - want[1]) * size)
    k = int(np.argmin(d))
    x, y = int(xs[k]), int(ys[k])
    off = float(d[k])
    return {"pixel": [x, y], "offPx": round(off, 2), "seen": off <= max(2.0, 1.5 * footprint(uv, x, y, size))}


def painted_on_screen(uv: np.ndarray, item: np.ndarray, alphas: dict) -> tuple[np.ndarray, np.ndarray]:
    """(seen, painted): (h, w) bool masks over the shot's picture. seen = a pixel showing one of the items of `alphas`
    ({index into the picture's items: (S, S) canvas alpha 0..1}); painted = seen and painted there."""
    seen = np.zeros(item.shape, bool)
    painted = np.zeros(item.shape, bool)
    for idx, alpha in alphas.items():
        mine = item == idx
        seen |= mine
        painted |= mine & (sample(alpha, uv) >= PAINTED_AT)
    return seen, painted


def hatch(rgb: np.ndarray, where: np.ndarray, spacing: int = 12, strength: float = 0.55) -> np.ndarray:
    """`rgb` (h, w, 3 uint8) with diagonal orange stripes over `where` (h, w bool) and a faint orange wash."""
    h, w = where.shape
    yy, xx = np.mgrid[0:h, 0:w]
    stripe = ((xx + yy) // (spacing // 2)) % 2 == 0
    k = np.where(where & stripe, strength, np.where(where, 0.18, 0.0))[..., None]
    return (rgb.astype(np.float32) * (1 - k) + np.asarray(HATCH, np.float32) * k + 0.5).astype(np.uint8)


def box(points, size_px: float, canvas: int | None = None) -> list[int] | None:
    """Canvas-px box [x0, y0, x1, y1] a path with a brush of `size_px` covers (points [[x, y, …], …]), inside a
    `canvas` px square when given."""
    if not points:
        return None
    p = np.asarray([q[:2] for q in points], np.float64)
    r = size_px / 2
    b = [int(np.floor(p[:, 0].min() - r)), int(np.floor(p[:, 1].min() - r)), int(np.ceil(p[:, 0].max() + r)), int(np.ceil(p[:, 1].max() + r))]
    return [min(max(v, 0), canvas) for v in b] if canvas else b


def uv_box(px_box, size: int) -> list[float] | None:
    """The uv box [u0, v0, u1, v1] of a canvas-px box."""
    if not px_box:
        return None
    x0, y0, x1, y1 = px_box
    return [round(x0 / size, 4), round(1 - y1 / size, 4), round(x1 / size, 4), round(1 - y0 / size, 4)]


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def stroke_line(r: dict) -> str:
    """One stroke's report: "stroke s3 (From the view, Hero 01): landed on case and lid, at most 1.2 screen px outside the
    line"; one not landed: its verdict ("painted in 30 pieces, up to 49 screen px outside the line on lid")."""
    how = "From the view" + (f', {r["shot"]}' if r.get("shot") else "") if r.get("view") else (
        "on the surface, by anchors" if r.get("anchored") else "on the surface")
    head = f'stroke {r["stroke"]} ({how}, layer {r["layer"]})'
    if not r.get("landed"):
        return f'{head}: {r.get("verdict") or "laid no paint"}'
    off = "" if r.get("offPx") is None else f', at most {r["offPx"]:.1f} screen px outside the line' if r.get("view") \
        else f', {r["offPx"]:.1f} canvas px off'
    where = f' on {_and(r["items"])}' if r.get("items") else ""
    at = f' (canvas x {r["box"][0]}–{r["box"][2]}, y {r["box"][1]}–{r["box"][3]})' if r.get("box") else ""
    worse = f'; {r["verdict"]}' if r.get("verdict") and r["verdict"] != "landed" else ""
    return f'{head}: landed{where}{off}{at}{worse}'
