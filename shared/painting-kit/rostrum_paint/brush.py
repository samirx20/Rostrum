"""The brush engine: stamps one stroke into one RGBA layer (carried over from P-PAINT, `proofs/paint/kit/brush.py`).

`stamp_stroke` changes the layer in place and returns the stroke's `Coverage` (the most alpha any stamp laid on each
pixel, before wet / mode, inside its bbox), so the canvas knows which stroke last touched each pixel and `landed` can
check where it went. Same inputs + seed = same pixels: that is what makes replay and the pixel cache exact.
"""
import colorsys, math
import numpy as np

from .marks import ALONG, K, MODES, PARAMS, TIPS, Coverage, Paper, _noise1, _ss, _up, apply_paint


def check(brush, params):
    bad = set(params) - set(PARAMS)
    if bad:
        raise ValueError(f"unknown brush settings {sorted(bad)}; known: {sorted(PARAMS)}")
    if brush not in TIPS:
        raise ValueError(f"brush must be one of {TIPS}, got {brush!r}")
    if params.get("mode", "normal") not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {params['mode']!r}")


def stamp_stroke(layer, points, color, size, brush="round", *, mask=None, under=None, paper=None, **params):
    """Paint one stroke into `layer` (HxWx4 premultiplied float32, changed in place).

    points: (x, y[, pressure[, tilt]]) in layer pixels. mask: HxW 0..1 or None. under: HxWx3
    composite below this layer, needed for `sample_all=True`. Returns Coverage (or None if the
    stroke is entirely off the layer)."""
    check(brush, params)
    p = {**PARAMS, **params}
    wet, cj, sp, tip = float(p["wet"]), p["color_jitter"], p["size_pressure"], brush
    if p["sample_all"] and under is None:
        raise ValueError("sample_all=True needs the composite below the layer (under=...)")
    H, W = layer.shape[:2]
    rng = np.random.default_rng(p["seed"])
    pts = np.array([(q[0], q[1], q[2] if len(q) > 2 else 1.0) for q in points], float)
    if not len(pts):
        raise ValueError("a stroke needs at least one point")
    # resample the path: one stamp every spacing * (local tip length) pixels
    seg = np.hypot(*np.diff(pts[:, :2], axis=0).T) if len(pts) > 1 else np.zeros(0)
    L = np.concatenate([[0], np.cumsum(seg)])
    step = max(0.3 if tip == "line" else 0.5, p["spacing"] * size * ALONG[tip] * (0.6 if wet > 0 else 2))
    t = [0.0]
    while t[-1] < L[-1]:
        pr = np.interp(t[-1], L, pts[:, 2])
        t.append(t[-1] + max(0.3, step * (1 - sp * (1 - pr))))
    t = np.minimum(np.array(t), L[-1])
    X, Y, Pr = (np.interp(t, L, pts[:, k]) if L[-1] > 0 else pts[:1, k] for k in range(3))
    S = t / L[-1] if L[-1] > 0 else np.zeros(1)
    n = len(t)
    th = (np.arctan2(np.gradient(Y), np.gradient(X)) if n > 1 else np.zeros(1)) if p["angle"] is None \
        else np.full(n, math.radians(p["angle"]))
    X = X + rng.normal(0, p["jitter"] * size, n)
    Y = Y + rng.normal(0, p["jitter"] * size, n)
    R = (size / 2) * (1 - sp * (1 - Pr))
    A = p["opacity"] * (1 - p["opacity_pressure"] * (1 - Pr))
    A, R = A * np.minimum(1, R / 0.5), np.maximum(R, 0.5)  # thinner than a pixel fades, never breaks
    Kr = max(K, int(2 * R.max()) + 1)
    # per-stroke tip profile across the brush: bristles, ragged start/end, colour streaks
    v = np.linspace(-1, 1, Kr)
    if tip == "bristle":
        nb = int(np.clip(size / 2, 10, 60))
        prof = np.zeros(Kr)
        for c, w_, s_ in zip(rng.uniform(-.95, .95, nb), rng.uniform(.04, .1, nb), rng.uniform(.4, 1, nb)):
            prof = np.maximum(prof, s_ * np.exp(-((v - c) / w_) ** 2))
        prof = 0.7 * prof + 0.3 * _up(_noise1(K, 8, rng), Kr)
    elif tip == "flat":
        prof = 0.75 + 0.25 * _up(_noise1(K, 4, rng), Kr)
    elif tip == "block":
        prof = 0.88 + 0.12 * _up(_noise1(K, 6, rng), Kr)
    else:
        prof = np.ones(Kr)
    rag = {"bristle": (0.12, 0.35, 1.5), "flat": (0.08, 0.2, 5), "block": (0.25, 0.25, 5)}.get(tip, (0, 0, 8))
    start = rag[0] * _up(_noise1(K, rag[2], rng), Kr)
    end = rag[1] * _up(_noise1(K, rag[2], rng), Kr)
    streak = (_up(_noise1(K, 2 if tip == "bristle" else 6, rng), Kr) - 0.5) * 2
    hn, sn, vn = ((_noise1(n, max(2, size / step), rng) - 0.5) * 2 for _ in range(3))
    wv = 1 - 0.05 * _noise1(n, max(2, size / step), rng) if tip == "block" else None
    h0, s0, v0 = colorsys.rgb_to_hsv(*np.clip(color, 0, 1))
    cols = np.array([colorsys.hsv_to_rgb((h0 + p["hue_jitter"] / 360 * a) % 1, np.clip(s0 * (1 + cj * b), 0, 1),
                                         np.clip(v0 * (1 + cj * c), 0, 1)) for a, b, c in zip(hn, sn, vn)], np.float32)
    G, F = (paper or Paper(H, W)).fields() if p["grain"] > 0 or tip == "chalk" else (None, None)
    soft = max(1 - p["hardness"], 0.03)
    bx0 = int(max(0, np.floor((X - R).min()) - 1)); bx1 = int(min(W, np.ceil((X + R).max()) + 2))
    by0 = int(max(0, np.floor((Y - R).min()) - 1)); by1 = int(min(H, np.ceil((Y + R).max()) + 2))
    if bx1 <= bx0 or by1 <= by0:
        return None
    cov = np.zeros((by1 - by0, bx1 - bx0), np.float32)  # max coverage so far in this stroke
    D, res = int(2 * R.max()) + 6, None
    for i in range(n):
        r = R[i]
        x0, x1 = max(bx0, int(X[i] - r) - 1), min(bx1, int(X[i] + r) + 2)
        y0, y1 = max(by0, int(Y[i] - r) - 1), min(by1, int(Y[i] + r) + 2)
        if x1 <= x0 or y1 <= y0:
            continue
        dx = (np.arange(x0, x1, dtype=np.float32) - np.float32(X[i]))[None, :]
        dy = (np.arange(y0, y1, dtype=np.float32) - np.float32(Y[i]))[:, None]
        c, s = math.cos(th[i]), math.sin(th[i])
        u, vv = (dx * c + dy * s) / r, (dy * c - dx * s) / r
        idx = ((np.clip(vv, -1, 1) + 1) * (Kr - 1) / 2).astype(np.int32)
        if tip in ("round", "chalk"):
            a = _ss((r - np.sqrt(dx * dx + dy * dy)) / max(1.0, soft * r))
            if tip == "chalk":
                a = _ss((a - 0.85 * (1 - F[y0:y1, x0:x1])) / 0.3)
        elif tip == "line":
            a = np.clip(r + 0.5 - np.sqrt(dx * dx + dy * dy), 0, 1)
        elif tip == "bristle":
            a = _ss((1 - (u / ALONG[tip]) ** 2 - vv * vv) / soft)
        elif tip == "flat":
            a = _ss((1 - np.abs(u) / ALONG[tip]) / soft) * _ss((1 - np.abs(vv)) / (soft * 0.3))
        else:  # block: crisp rectangle, square ends with slight raggedness
            ew = max(1.0, soft * r * 0.15)
            al = t[i] + u * r  # distance along the stroke
            a = (_ss((wv[i] - np.abs(vv)) * r / ew) * _ss((ALONG[tip] - np.abs(u)) * r / ew)
                 * _ss((al + ALONG[tip] * R[0] - start[idx] * R[0]) / ew)
                 * _ss((L[-1] + ALONG[tip] * R[-1] - end[idx] * R[-1] - al) / ew) * prof[idx])
        if tip in ("bristle", "flat"):
            a = a * (prof * _ss((S[i] - start) / 0.06) * _ss((1 - end - S[i]) / 0.06))[idx]
        a = a * A[i]
        if G is not None and p["grain"] > 0:
            tg = p["grain"] * (1 - G[y0:y1, x0:x1])
            a = np.clip((a - tg) / (1.001 - tg), 0, 1)
        if mask is not None:
            a = a * mask[y0:y1, x0:x1]
        cv = cov[y0 - by0:y1 - by0, x0 - bx0:x1 - bx0]
        c1 = np.maximum(cv, a)
        inc = (c1 - cv) / (1.0001 - cv)
        cv[...] = c1
        col = cols[i] * (1 + cj * 0.6 * streak[idx])[..., None]
        region = layer[y0:y1, x0:x1]
        if wet > 0:  # smudge: the brush carries a reservoir of the paint it passed over
            oy, ox = int(round(Y[i])) - D // 2, int(round(X[i])) - D // 2
            win = (slice(y0 - oy, y1 - oy), slice(x0 - ox, x1 - ox))
            if 0 <= oy and oy + D <= H and 0 <= ox and ox + D <= W:
                ix = (slice(oy, oy + D), slice(ox, ox + D))
            else:  # near the edge: clamp, the canvas edge repeats
                ix = np.ix_(np.clip(np.arange(oy, oy + D), 0, H - 1), np.clip(np.arange(ox, ox + D), 0, W - 1))
            pick = layer[ix].copy()
            if p["sample_all"]:  # what the eye sees: this layer over the composite below
                pick[..., :3] += (1 - pick[..., 3:]) * under[ix]
                pick[..., 3] = 1
            if res is None:
                res = pick
            lt = math.hypot(X[i] - X[i - 1], Y[i] - Y[i - 1]) / (2 * r * ALONG[tip]) if i else 0
            region += (a * (1 - (1 - 0.97 * wet) ** max(lt, 0.05)))[..., None] * (res[win] - region)
            res += (1 - (0.6 * wet) ** max(lt, 0.05)) * (pick - res)
        apply_paint(region, inc * (1 - wet), col, p["mode"])
    return Coverage(cov, (bx0, by0, bx1, by1))
