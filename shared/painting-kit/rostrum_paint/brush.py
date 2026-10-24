"""The brush engine: stamps one stroke into one RGBA layer (carried over from P-PAINT, `proofs/paint/kit/brush.py`).

`stamp_stroke` changes the layer in place and returns the stroke's `Coverage` (the most alpha any stamp laid on each
pixel, before wet / mode, inside its bbox), so the canvas knows which stroke last touched each pixel and `landed` can
check where it went. Same inputs + seed = same pixels: that is what makes replay and the pixel cache exact.

Two halves: `plan` (the path, the random draws, the tip profiles, every dab's numbers) and the dabs laid with it,
by `dabs` here or by the 2D engine's native stamper (`native.py`), which gives the same pixels, bit for bit.
"""
import colorsys, math
from types import SimpleNamespace
import numpy as np

from . import shape as shaping
from . import pictures, wrap
from .marks import ALONG, EVEN, K, MODES, PARAMS, TIPS, UNDER, Coverage, Paper, _noise1, _ss, _up, apply_paint


def check(brush, params):
    bad = set(params) - set(PARAMS)
    if bad:
        raise ValueError(f"unknown brush settings {sorted(bad)}; known: {sorted(PARAMS)}")
    if brush not in TIPS:
        raise ValueError(f"brush must be one of {TIPS}, got {brush!r}")
    if params.get("mode", "normal") not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {params['mode']!r}")
    pictures.tip(params.get("texture", "none"))     # an unknown or missing picture fails here, naming itself


def stamp_stroke(layer, points, color, size, brush="round", *, mask=None, under=None, paper=None, lay=None, **params):
    """Paint one stroke into `layer` (HxWx4 premultiplied float32, changed in place).

    points: (x, y[, pressure[, tilt x°, tilt y°]]) in layer pixels. mask: HxW 0..1 or None. under: HxWx3
    composite below this layer, needed for `sample_all=True`. lay: what lays the dabs (`dabs`, or the native
    stamper's). Returns Coverage (or None if the stroke is entirely off the layer)."""
    check(brush, params)
    if params.get("sample_all") and under is None:
        raise ValueError("sample_all=True needs the composite below the layer (under=...)")
    P = plan(layer.shape[:2], points, color, size, brush, paper, params)
    return None if P is None else (lay or dabs)(layer, P, mask, under)


def plan(shape, points, color, size, tip, paper, params):
    """Everything a stroke's dabs need, drawn from its seed; None if the stroke is entirely off the layer."""
    p = {**PARAMS, **params}
    wet, cj, sp = float(p["wet"]), p["color_jitter"], p["size_pressure"]
    H, W = shape
    rng = np.random.default_rng(p["seed"])
    if not len(points):
        raise ValueError("a stroke needs at least one point")
    full = shaping.steady(shaping.points(points), p["steady"])     # x, y, pressure, tilt x, tilt y
    pts = full[:, :3]
    # resample the path: one stamp every spacing * (local tip length) pixels
    seg = np.hypot(*np.diff(pts[:, :2], axis=0).T) if len(pts) > 1 else np.zeros(0)
    L = np.concatenate([[0], np.cumsum(seg)])
    step = max(0.3 if tip == "line" else 0.5, p["spacing"] * size * ALONG[tip] * (0.6 if wet > 0 else 2))
    if p["even"] and tip not in ("line", "block"):   # a soft edge shows the dabs as ridges unless they come closer
        r0 = size / 2
        step = min(step, max(0.5, EVEN * math.sqrt(r0 * max(1.0, (1 - p["hardness"]) * r0))))
    t = [0.0]
    while t[-1] < L[-1]:
        pr = np.interp(t[-1], L, pts[:, 2])
        t.append(t[-1] + max(0.3, step * (1 - sp * (1 - pr)) * shaping.step_scale(t[-1], L[-1], size, p)))
    t = np.minimum(np.array(t), L[-1])
    X, Y, Pr = (np.interp(t, L, pts[:, k]) if L[-1] > 0 else pts[:1, k] for k in range(3))
    S = t / L[-1] if L[-1] > 0 else np.zeros(1)
    n = len(t)
    th = (np.arctan2(np.gradient(Y), np.gradient(X)) if n > 1 else np.zeros(1)) if p["angle"] is None \
        else np.full(n, math.radians(p["angle"]))
    X = X + rng.normal(0, p["jitter"] * size, n)
    Y = Y + rng.normal(0, p["jitter"] * size, n)
    R = (size / 2) * (1 - sp * (1 - Pr))
    th, R = shaping.dabs(p, th, R, t, L, full, size, p["seed"])
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
    cols = _hsv_to_rgb((h0 + p["hue_jitter"] / 360 * hn) % 1, np.clip(s0 * (1 + cj * sn), 0, 1),
                       np.clip(v0 * (1 + cj * vn), 0, 1)).astype(np.float32)
    G, F = (paper or Paper(H, W)).fields() if p["grain"] > 0 or tip == "chalk" else (None, None)
    soft = max(1 - p["hardness"], 0.03)
    # wet carry: how much each dab lays of the reservoir and takes up (from the path as drawn, before any wrap)
    wetk = [(0.0, 0.0)] * n
    if wet > 0:
        wetk = []
        for i in range(n):
            lt = math.hypot(X[i] - X[i - 1], Y[i] - Y[i - 1]) / (2 * R[i] * ALONG[tip]) if i else 0
            wetk.append((1 - (1 - 0.97 * wet) ** max(lt, 0.05), 1 - (0.6 * wet) ** max(lt, 0.05)))
    again = None
    if p["wrap"]:       # seamless (wrap.py): each dab as its parts, the canvas's opposite edges joined
        i, X, Y, again, last = wrap.parts(H, W, X, Y, R)
        R, A, t, S, th, cols = R[i], A[i], t[i], S[i], th[i], cols[i]
        wv = None if wv is None else wv[i]
        wetk = [(wetk[k][0], wetk[k][1] if e else 0.0) for k, e in zip(i.tolist(), last.tolist())]
        n = len(i)
    bx0 = int(max(0, np.floor((X - R).min()) - 1)); bx1 = int(min(W, np.ceil((X + R).max()) + 2))
    by0 = int(max(0, np.floor((Y - R).min()) - 1)); by1 = int(min(H, np.ceil((Y + R).max()) + 2))
    if bx1 <= bx0 or by1 <= by0:
        return None
    D = int(2 * R.max()) + 6
    # each dab's box (empty: skipped), turn, and wet carry (the reservoir's place, how much it lays and takes up)
    box = np.stack([np.maximum(bx0, np.trunc(X - R).astype(int) - 1), np.minimum(bx1, np.trunc(X + R).astype(int) + 2),
                    np.maximum(by0, np.trunc(Y - R).astype(int) - 1), np.minimum(by1, np.trunc(Y + R).astype(int) + 2)], 1)
    cs = [(math.cos(v), math.sin(v)) for v in th.tolist()]
    at = np.zeros((n, 2), int)
    if wet > 0:
        at = np.stack([np.round(Y).astype(int) - D // 2, np.round(X).astype(int) - D // 2], 1)
    return SimpleNamespace(tip=tip, mode=p["mode"], tex=pictures.tip(p["texture"]), wet=wet, cj=cj, sample_all=bool(p["sample_all"]),
                           grain=p["grain"], soft=soft, n=n, X=X, Y=Y, R=R, A=A, t=t, S=S, L=L, Kr=Kr, prof=prof,
                           start=start, end=end, streak=streak, wv=wv, cols=cols, G=G, F=F,
                           bbox=(bx0, by0, bx1, by1), D=D, box=box, cs=cs, wetk=wetk, at=at, wrap=bool(p["wrap"]),
                           again=again)


def _hsv_to_rgb(h, s, v):
    """colorsys.hsv_to_rgb over arrays, step for step (the same numbers)."""
    i = np.trunc(h * 6.0)
    f = (h * 6.0) - i
    p, q, t = v * (1.0 - s), v * (1.0 - s * f), v * (1.0 - s * (1.0 - f))
    i = i.astype(int) % 6
    pick = lambda *c: np.choose(i, c)  # noqa: E731
    return np.stack([pick(v, q, p, p, t, v), pick(t, v, v, q, p, p), pick(p, p, t, v, v, q)], 1)


def _texture(T, u, v):
    """The tip picture under the dab (bilinear; u along the tip, v across, -1..1 each). The native stamper repeats
    these steps in the same order and precision."""
    n = T.shape[0]
    fx = (np.clip(u, -1, 1) + 1) * (n - 1) / 2
    fy = (np.clip(v, -1, 1) + 1) * (n - 1) / 2
    x0, y0 = np.minimum(fx.astype(np.int32), n - 2), np.minimum(fy.astype(np.int32), n - 2)
    gx, gy = fx - x0, fy - y0
    return ((T[y0, x0] * (1 - gx) + T[y0, x0 + 1] * gx) * (1 - gy)
            + (T[y0 + 1, x0] * (1 - gx) + T[y0 + 1, x0 + 1] * gx) * gy)


def dabs(layer, P, mask=None, under=None):
    """Lays a planned stroke's dabs into `layer` (numpy); its Coverage."""
    H, W = layer.shape[:2]
    tip, wet, cj, soft, G, F, R, t, S = P.tip, P.wet, P.cj, P.soft, P.G, P.F, P.R, P.t, P.S
    prof, start, end, streak, Kr = P.prof, P.start, P.end, P.streak, P.Kr
    bx0, by0, bx1, by1 = P.bbox
    cov = np.zeros((by1 - by0, bx1 - bx0), np.float32)  # max coverage so far in this stroke
    D, res = P.D, None
    under0 = layer[by0:by1, bx0:bx1].copy() if P.mode in UNDER else None   # what was under the stroke
    for i in range(P.n):
        r = R[i]
        x0, x1, y0, y1 = P.box[i].tolist()
        if x1 <= x0 or y1 <= y0:
            continue
        dx = (np.arange(x0, x1, dtype=np.float32) - np.float32(P.X[i]))[None, :]
        dy = (np.arange(y0, y1, dtype=np.float32) - np.float32(P.Y[i]))[:, None]
        c, s = P.cs[i]
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
            a = (_ss((P.wv[i] - np.abs(vv)) * r / ew) * _ss((ALONG[tip] - np.abs(u)) * r / ew)
                 * _ss((al + ALONG[tip] * R[0] - start[idx] * R[0]) / ew)
                 * _ss((P.L[-1] + ALONG[tip] * R[-1] - end[idx] * R[-1] - al) / ew) * prof[idx])
        if tip in ("bristle", "flat"):
            a = a * (prof * _ss((S[i] - start) / 0.06) * _ss((1 - end - S[i]) / 0.06))[idx]
        if P.tex is not None:
            a = a * _texture(P.tex, u / ALONG[tip], vv)
        a = a * P.A[i]
        if G is not None and P.grain > 0:
            tg = P.grain * (1 - G[y0:y1, x0:x1])
            a = np.clip((a - tg) / (1.001 - tg), 0, 1)
        if mask is not None:
            a = a * mask[y0:y1, x0:x1]
        cv = cov[y0 - by0:y1 - by0, x0 - bx0:x1 - bx0]
        c0, c1 = cv.copy(), np.maximum(cv, a)
        cv[...] = c1
        col = P.cols[i] * (1 + cj * 0.6 * streak[idx])[..., None]
        region = layer[y0:y1, x0:x1]
        if wet > 0:  # smudge: the brush carries a reservoir of the paint it passed over
            oy, ox = P.at[i].tolist()
            win = (slice(y0 - oy, y1 - oy), slice(x0 - ox, x1 - ox))
            if P.again is None or not P.again[i]:   # another part of the same dab reuses its pick-up (wrap.py)
                if 0 <= oy and oy + D <= H and 0 <= ox and ox + D <= W:
                    ix = (slice(oy, oy + D), slice(ox, ox + D))
                elif P.wrap:  # near a joined edge: the paint across it
                    ix = np.ix_(wrap.ring(oy, D, H), wrap.ring(ox, D, W))
                else:  # near the edge: clamp, the canvas edge repeats
                    ix = np.ix_(np.clip(np.arange(oy, oy + D), 0, H - 1), np.clip(np.arange(ox, ox + D), 0, W - 1))
                pick = layer[ix].copy()
                if P.sample_all:  # what the eye sees: this layer over the composite below
                    pick[..., :3] += (1 - pick[..., 3:]) * under[ix]
                    pick[..., 3] = 1
            if res is None:
                res = pick
            lay, take = P.wetk[i]
            region += (a * lay)[..., None] * (res[win] - region)
            res += take * (pick - res)
        apply_paint(region, c0, c1, col, P.mode, 1 - wet,
                    None if under0 is None else under0[y0 - by0:y1 - by0, x0 - bx0:x1 - bx0])
    return Coverage(cov, P.bbox)
