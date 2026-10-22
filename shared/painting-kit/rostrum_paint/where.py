"""The agent's "where" tools on a canvas: `what` is at a pixel, and did a stroke `land` where it was meant.
Both read the canvas item (the truth) and its cached pixels; `landed` re-stamps only the one stroke it checks.
`landed` is P-PAINT's measure (`proofs/paint/kit/where.py`): across the path's normal, where does the stroke's
paint centre, and how far is that from the path."""
from __future__ import annotations

import numpy as np

from . import canvas as C
from .compose import mask_array

END_SHARE = 0.08   # share of the path at each end left out: brushes taper and fray there on purpose
MAX_FACTOR = 3.0   # the worst sample may be this many times the mean limit (corners round off)


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in c[:3])


def _check_xy(w, h, x, y):
    if not (0 <= x < w and 0 <= y < h):
        raise ValueError(f"({x}, {y}) is outside the {w}×{h} canvas")


def what(canvas: dict, w: int, h: int, x: float, y: float) -> dict:
    """Colour at (x, y), each paint layer's colour there, the top stroke (`stroke`), and the masks it is inside."""
    x, y = int(x), int(y)
    _check_xy(w, h, x, y)
    pix = C.render(canvas, w, h)
    seen = C.compose.straight8(pix.rgba[y:y + 1, x:x + 1])[0, 0]
    layers = []
    for paint in canvas.get("paints", []):
        px = C.layer_rgba(canvas, paint["id"], w, h)[y, x]
        layers.append({"id": paint["id"], "name": paint["name"], "color": _hex(px), "alpha": round(px[3] / 255, 3),
                       "visible": paint["visible"], "mode": paint["mode"]})
    top = int(pix.top[y, x])
    masks = [m["id"] for m in canvas.get("paintmasks", []) if mask_array(m, w, h)[y, x] > 0.5]
    return {"x": x, "y": y, "color": _hex(seen), "alpha": round(seen[3] / 255, 3), "layers": layers,
            "stroke": pix.order[top] if top >= 0 else None, "inside_masks": masks}


def _find(canvas, stroke_id):
    for paint in canvas.get("paints", []):
        for s in paint["strokes"]:
            if s["id"] == stroke_id:
                return s
    raise KeyError(f"no stroke {stroke_id!r} in {canvas['id']}")


def coverage(canvas: dict, w: int, h: int, stroke_id: str) -> np.ndarray:
    """HxW 0..1: how much paint this one stroke laid (its own coverage, whatever is under or over it)."""
    s = _find(canvas, stroke_id)
    masks = {m["id"]: m for m in canvas.get("paintmasks", [])}
    out = np.zeros((h, w), np.float32)
    blank = np.zeros((h, w, 4), np.float32)
    cov = C.stamp(blank, {**s, "smudge": False}, w, h, masks)   # coverage never depends on wetness
    if cov is not None:
        x0, y0, x1, y1 = cov.bbox
        out[y0:y1, x0:x1] = cov.a
    return out


def _bilinear(a, xs, ys):
    h, w = a.shape
    xs, ys = np.clip(xs, 0, w - 1.001), np.clip(ys, 0, h - 1.001)
    x0, y0 = xs.astype(int), ys.astype(int)
    fx, fy = xs - x0, ys - y0
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy)
            + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)


def _resample(pts, step):
    p = np.asarray(pts, np.float64)[:, :2]
    seg = np.hypot(*np.diff(p, axis=0).T) if len(p) > 1 else np.zeros(0)
    keep = np.concatenate([[True], seg > 1e-9])
    p, seg = p[keep], seg[seg > 1e-9]
    if len(p) == 1:
        return p, np.array([[1.0, 0.0]]), 0.0
    cum = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, cum[-1], max(2, int(cum[-1] / step) + 1))
    xy = np.stack([np.interp(t, cum, p[:, 0]), np.interp(t, cum, p[:, 1])], axis=1)
    i = np.clip(np.searchsorted(cum, t, side="right") - 1, 0, len(seg) - 1)
    return xy, (p[i + 1] - p[i]) / seg[i][:, None], float(cum[-1])


def landed(canvas: dict, w: int, h: int, stroke_id: str, path=None) -> dict:
    """Did the stroke's paint land on `path` (default: its own recorded path)? Mean / max px off, share painted."""
    s = _find(canvas, stroke_id)
    if s.get("type") == "fill":
        raise ValueError(f"{stroke_id} is a fill, not a stroke: it has no path to land on. Look at it with look_drawing")
    size, cov = float(s["size"]), coverage(canvas, w, h, stroke_id)
    if cov.sum() <= 1e-6:
        return {"stroke": stroke_id, "landed": False, "mean": None, "max": None,
                "verdict": f"missed: stroke {stroke_id} laid down no paint (off the canvas, or masked out)"}
    xy, tan, length = _resample(path if path is not None else s["points"], max(1.0, size / 4))
    nrm = np.stack([-tan[:, 1], tan[:, 0]], axis=1)
    offs = np.arange(-(size + 3), size + 3.01, 0.5)
    sx, sy = xy[:, :1] + nrm[:, :1] * offs[None], xy[:, 1:2] + nrm[:, 1:2] * offs[None]
    c = _bilinear(cov, sx, sy) * ((sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1))
    wsum = c.sum(axis=1)
    cen = (c * offs[None]).sum(axis=1) / np.maximum(wsum, 1e-9)
    painted = wsum > 0.25
    expected = (xy[:, 0] >= 0) & (xy[:, 0] <= w - 1) & (xy[:, 1] >= 0) & (xy[:, 1] <= h - 1)
    mask = s.get("mask")
    if mask:
        m = next(m for m in canvas["paintmasks"] if m["id"] == mask)
        expected &= _bilinear(mask_array(m, w, h), xy[:, 0], xy[:, 1]) > 0.5
    u = np.linspace(0, 1, len(xy))
    body = expected & (u >= END_SHARE) & (u <= 1 - END_SHARE)
    body = body if body.any() else expected
    res = {"stroke": stroke_id, "size": size, "length": length,
           "painted_share": float((body & painted).sum() / max(1, body.sum())),
           "clipped_length": float((~expected).sum()) * length / max(1, len(xy) - 1)}
    use = expected & painted
    if not use.any():
        return {**res, "landed": False, "mean": None, "max": None,
                "verdict": f"missed: no paint near the path of stroke {stroke_id}"}
    d = np.abs(cen[use])
    tol = max(2.0, 0.10 * size)
    res.update(mean=float(d.mean()), max=float(d.max()), tolerance=tol, max_tolerance=MAX_FACTOR * tol)
    if res["painted_share"] < 0.5:
        verdict = f"missed: only {res['painted_share'] * 100:.0f}% of the path got paint"
    elif res["mean"] > tol:
        verdict = f"missed by {res['mean']:.1f} px on average"
    elif res["max"] > MAX_FACTOR * tol:
        verdict = f"missed in one place by {res['max']:.1f} px"
    else:
        verdict = "landed"
    return {**res, "landed": verdict == "landed", "verdict": verdict}


def landed_text(r: dict) -> str:
    if r.get("mean") is None:
        return r["verdict"]
    return (f"stroke {r['stroke']}: {r['verdict']}\n"
            f"  paint centre vs path: mean {r['mean']:.2f} px, worst {r['max']:.2f} px (landed = mean <= "
            f"{r['tolerance']:.1f} px and worst <= {r['max_tolerance']:.1f} px)\n"
            f"  path {r['length']:.0f} px, {r['painted_share'] * 100:.0f}% of it got paint (ends left out), "
            f"{r['clipped_length']:.0f} px off the canvas or outside its mask")
