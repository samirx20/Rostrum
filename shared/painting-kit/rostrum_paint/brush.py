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
from .marks import ALONG, EVEN, K, MODES, PARAMS, TIPS, UNDER, Coverage, Paper, _noise1, _noise1_by_dab, _ss, _up, apply_paint


def check(brush, params):
    bad = set(params) - set(PARAMS)
    if bad:
        raise ValueError(f"unknown brush settings {sorted(bad)}; known: {sorted(PARAMS)}")
    if brush not in TIPS:
        raise ValueError(f"brush must be one of {TIPS}, got {brush!r}")
    if params.get("mode", "normal") not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {params['mode']!r}")
    pictures.tip(params.get("texture", "none"))     # an unknown or missing picture fails here, naming itself


class Carry:
    """What a stroke laid in pieces (`stamp_stroke`'s `piece`) hands from one piece to the next: the coverage it laid
    (`cov`, HxW float32 like the layer; made at the first piece when None; a caller whose layer grows may swap in a
    bigger one, the old one copied into its place), the wet reservoir after the last dab laid (`res`, D x D x 4,
    None until a wet dab picked up) and the first dab the next piece lays (`next`) and where it lies (`ahead`: x, y
    in the layer's px, None when every dab is laid): an open stroke holds back its dab at the pen (the last laid is up
    to a spacing behind the newest point), so the next piece's room must reach back to it."""

    def __init__(self, cov=None):
        self.cov, self.res, self.next, self.ahead = cov, None, 0, None


def stamp_stroke(layer, points, color, size, brush="round", *, mask=None, under=None, paper=None, lay=None, carry=None,
                 piece=None, **params):
    """Paint one stroke into `layer` (HxWx4 premultiplied float32, changed in place).

    points: (x, y[, pressure[, tilt x°, tilt y°]]) in layer pixels. mask: HxW 0..1 or None. under: HxWx3
    composite below this layer, needed for `sample_all=True`. lay: what lays the dabs (`dabs`, or the native
    stamper's). carry: HxW float32, the coverage the stroke already laid (a stroke drawn in pieces, as the wet ink
    does: each piece goes on where the last left off, so where they overlap nothing is laid twice); updated in place.

    piece: (from_t, open), one stroke laid in pieces while the pen draws it: `points` is the whole stroke so far,
    `carry` a `Carry` (the same one every piece), and only the dabs not laid yet (from `carry.next`, and at least
    `from_t` px along the stroke) are laid, the reservoir going on from the last piece, so the pieces lay the pixels
    the whole stroke laid at once does. `open`: the pen is still down: its last dab (at the pen, where the finished
    stroke has none) waits, and the end has no raggedness or taper yet; the last piece (open False) lays the end. Needs the
    stroke's `by_dab` draws. The start's raggedness is sized in brush sizes, as the finished stroke's.
    Returns Coverage (or None if the stroke, or the piece, is entirely off the layer)."""
    check(brush, params)
    if params.get("sample_all") and under is None:
        raise ValueError("sample_all=True needs the composite below the layer (under=...)")
    if piece is not None:
        return _piece(layer, points, color, size, brush, mask, under, paper, lay, carry, piece, params)
    P = plan(layer.shape[:2], points, color, size, brush, paper, params)
    if P is None:
        return None
    if carry is None:
        return (lay or dabs)(layer, P, mask, under)
    bx0, by0, bx1, by1 = P.bbox
    got = (lay or dabs)(layer, P, mask, under, np.ascontiguousarray(carry[by0:by1, bx0:bx1], np.float32))
    carry[by0:by1, bx0:bx1] = got.a
    return got


def _piece(layer, points, color, size, brush, mask, under, paper, lay, carry, piece, params):
    if not isinstance(carry, Carry):
        raise ValueError("a stroke laid in pieces carries a brush.Carry from piece to piece (carry=Carry())")
    from_t, open_ = piece
    P = plan(layer.shape[:2], points, color, size, brush, paper, params, (carry.next, float(from_t), bool(open_)))
    carry.next, carry.ahead = P.next, P.ahead
    if P.n == 0 or P.bbox is None:
        return None
    if carry.cov is None:
        carry.cov = np.zeros(layer.shape[:2], np.float32)
    if carry.cov.shape != layer.shape[:2]:
        raise ValueError(f"the carried coverage is {carry.cov.shape}, the layer {layer.shape[:2]}")
    if carry.res is not None and carry.res.shape != (P.D, P.D, 4):
        raise ValueError(f"the carried reservoir is {carry.res.shape}, this piece's {(P.D, P.D, 4)}")
    bx0, by0, bx1, by1 = P.bbox
    res_in = carry.res is not None
    res = carry.res if res_in else np.zeros((P.D, P.D, 4), np.float32) if P.wet > 0 else None
    got = (lay or dabs)(layer, P, mask, under, np.ascontiguousarray(carry.cov[by0:by1, bx0:bx1], np.float32),
                        res=res, res_in=res_in)
    carry.cov[by0:by1, bx0:bx1] = got.a
    if res is not None and (res_in or any(x1 > x0 and y1 > y0 for x0, x1, y0, y1 in P.box.tolist())):
        carry.res = res
    return got


def plan(shape, points, color, size, tip, paper, params, piece=None):
    """Everything a stroke's dabs need, drawn from its seed; None if the stroke is entirely off the layer.

    `by_dab` draws (a stroke setting; absent on strokes made before it: the older draws, their pixels kept): every
    random number of dab i is drawn the same however many dabs the stroke has, from a stream of its own, and the tip
    profile before any of them, so the stroke so far is the start of the whole stroke (the older draws come after a
    draw per dab: each extra dab moved the bristles). The tip's samples across (Kr) and the reservoir's side (D) are
    sized by the biggest the tip can be, not the biggest it was so far. A bristle or flat tip's ragged start and end
    reach about a brush size into the stroke (shape.fray), not a share of its length, so the start doesn't change as
    the stroke goes on.
    piece: (first dab, from_t, open), stamp_stroke's: the plan is of the whole stroke so far, but only its dabs from
    `first` on and at least `from_t` along are kept (P.next: the next piece's first dab; P.n 0: none to lay, P.bbox
    None: none on the layer)."""
    p = {**PARAMS, **params}
    wet, cj, sp = float(p["wet"]), p["color_jitter"], p["size_pressure"]
    by_dab = bool(p["by_dab"])
    first, from_t, open_ = piece or (0, 0.0, False)
    if piece is not None and not by_dab:
        raise ValueError("a stroke laid in pieces needs by_dab draws (by_dab=True): with the older draws each piece "
                         "would draw its own bristles")
    if open_:
        p["taper_end"] = 0.0
    sized = math.inf if open_ else None             # an open stroke's taper start is sized as the finished one's
    seed = p["seed"]
    H, W = shape
    rng = np.random.default_rng([int(seed), 2] if by_dab else seed)
    if not len(points):
        raise ValueError("a stroke needs at least one point")
    full = shaping.steady(shaping.points(points), p["steady"], by_dab, open_)     # x, y, pressure, tilt x, tilt y
    pts = full[:, :3]
    # resample the path: one stamp every spacing * (local tip length) pixels
    seg = np.hypot(*np.diff(pts[:, :2], axis=0).T) if len(pts) > 1 else np.zeros(0)
    L = np.concatenate([[0], np.cumsum(seg)])
    step = max(0.3 if tip == "line" else 0.5, p["spacing"] * size * ALONG[tip] * (0.6 if wet > 0 else 2))
    if p["even"] and tip not in ("line", "block"):   # a soft edge shows the dabs as ridges unless they come closer
        r0 = size / 2
        step = min(step, max(0.5, EVEN * math.sqrt(r0 * max(1.0, (1 - p["hardness"]) * r0))))
    t = np.minimum(np.array(_spacing(L, pts[:, 2], step, sp, size, p, sized)), L[-1])
    X, Y, Pr = (np.interp(t, L, pts[:, k]) if L[-1] > 0 else pts[:1, k] for k in range(3))
    S = t / L[-1] if L[-1] > 0 else np.zeros(1)
    n = len(t)
    if p["angle"] is not None:
        th = np.full(n, math.radians(p["angle"]))
    elif n < 2:
        th = np.zeros(1)
    elif by_dab:        # from the dab before (the first: towards the next), so a dab's turn is known once it is placed
        th = np.arctan2(np.diff(Y), np.diff(X))
        th = np.concatenate([th[:1], th])
    else:
        th = np.arctan2(np.gradient(Y), np.gradient(X))
    if by_dab:
        X = X + p["jitter"] * size * np.random.default_rng([int(seed), 3]).standard_normal(n)
        Y = Y + p["jitter"] * size * np.random.default_rng([int(seed), 4]).standard_normal(n)
    else:
        X = X + rng.normal(0, p["jitter"] * size, n)
        Y = Y + rng.normal(0, p["jitter"] * size, n)
    R = (size / 2) * (1 - sp * (1 - Pr))
    th, R = shaping.dabs(p, th, R, t, L, full, size, seed, by_dab, sized)
    A = p["opacity"] * (1 - p["opacity_pressure"] * (1 - Pr))
    A, R = A * np.minimum(1, R / 0.5), np.maximum(R, 0.5)  # thinner than a pixel fades, never breaks
    most = R.max()
    if by_dab:          # the biggest the tip can be: full pressure, leaning on its side
        most = max(most, 0.5, (size / 2) * (1 + shaping.TILT_WIDEN * p["tilt_size"]))
    Kr = max(K, int(2 * most) + 1)
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
    if open_:           # the pen is still down: no ragged end yet
        end = np.full(Kr, -1e6)
    if by_dab and tip in ("bristle", "flat"):       # the ragged ends sized in brush sizes, not shares of the stroke
        S = shaping.fray(t, L[-1], size, rag, open_)
    if by_dab:
        noise = lambda salt: _noise1_by_dab(n, max(2, size / step), np.random.default_rng([int(seed), salt]))  # noqa: E731
        hn, sn, vn = ((noise(salt) - 0.5) * 2 for salt in (5, 6, 7))
        wv = 1 - 0.05 * noise(8) if tip == "block" else None
    else:
        hn, sn, vn = ((_noise1(n, max(2, size / step), rng) - 0.5) * 2 for _ in range(3))
        wv = 1 - 0.05 * _noise1(n, max(2, size / step), rng) if tip == "block" else None
    h0, s0, v0 = colorsys.rgb_to_hsv(*np.clip(color, 0, 1))
    cols = _hsv_to_rgb((h0 + p["hue_jitter"] / 360 * hn) % 1, np.clip(s0 * (1 + cj * sn), 0, 1),
                       np.clip(v0 * (1 + cj * vn), 0, 1)).astype(np.float32)
    G, F = (paper or Paper(H, W)).fields() if p["grain"] > 0 or tip == "chalk" else (None, None)
    soft = max(1 - p["hardness"], 0.03)
    r0, rl, length = R[0], R[-1], L[-1]     # the stroke's ends (a block's ragged ends), whatever part is laid
    lo, hi = 0, n
    if piece is not None:   # the dabs not laid yet; while open, not the last (it moves with the pen; the first turns towards it)
        hi = (n - 1 if n > 2 or p["angle"] is not None else 0) if open_ else n
        lo = min(hi, max(int(first), int(np.searchsorted(t, from_t, "left"))))
        if open_:
            length = math.inf
    ahead = (float(X[hi]), float(Y[hi])) if hi < n else None     # where the next piece's first dab lies
    # wet carry: how much each dab lays of the reservoir and takes up (from the path as drawn, before any wrap)
    wetk = [(0.0, 0.0)] * (hi - lo)
    if wet > 0:
        wetk = []
        for i in range(lo, hi):
            lt = math.hypot(X[i] - X[i - 1], Y[i] - Y[i - 1]) / (2 * R[i] * ALONG[tip]) if i else 0
            wetk.append((1 - (1 - 0.97 * wet) ** max(lt, 0.05), 1 - (0.6 * wet) ** max(lt, 0.05)))
    if piece is not None:
        X, Y, R, A, t, S, th, cols = (v[lo:hi] for v in (X, Y, R, A, t, S, th, cols))
        wv = None if wv is None else wv[lo:hi]
        n = hi - lo
        if n == 0:
            return SimpleNamespace(n=0, next=hi, ahead=ahead, bbox=None)
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
        return None if piece is None else SimpleNamespace(n=n, next=hi, ahead=ahead, bbox=None)
    D = int(2 * (most if by_dab else R.max())) + 6
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
                           again=again, r0=r0, rl=rl, length=length, next=hi, ahead=ahead)


def _spacing(L, pressure, step, sp, size, p, length=None) -> list:
    """Where the dabs go along the path (px from its start): one each `step`, closer where the pressure thins the tip
    (size_pressure `sp`) and where the taper does. One walk along the path, a dab at a time in plain floats: the
    pressure there is read as np.interp would, without its cost per dab (a long stroke has thousands). `length`: what
    the taper is sized by, if not the path's (an open stroke's)."""
    Ls, ps, total = L.tolist(), pressure.tolist(), float(L[-1])
    sized = total if length is None else length
    last, flat, j = len(Ls) - 1, all(v == ps[0] for v in ps), 0
    t = [0.0]
    while t[-1] < total:
        x = t[-1]
        if flat:
            pr = ps[0]
        else:
            while j < last and Ls[j + 1] <= x:
                j += 1
            pr = ps[j] if j == last or Ls[j] == x else (ps[j + 1] - ps[j]) / (Ls[j + 1] - Ls[j]) * (x - Ls[j]) + ps[j]
        t.append(x + max(0.3, step * (1 - sp * (1 - pr)) * shaping.step_scale(x, sized, size, p)))
    return t


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


def dabs(layer, P, mask=None, under=None, cov=None, res=None, res_in=False):
    """Lays a planned stroke's dabs into `layer` (numpy); its Coverage. `cov`: the stroke's coverage so far over its
    bbox (stamp_stroke's `carry`), else none yet. `res`: D x D x 4 float32, the wet reservoir to go on from
    (`res_in`; else it starts as the first dab's pick-up), left as it is after the last dab (a stroke in pieces)."""
    H, W = layer.shape[:2]
    tip, wet, cj, soft, G, F, R, t, S = P.tip, P.wet, P.cj, P.soft, P.G, P.F, P.R, P.t, P.S
    prof, start, end, streak, Kr = P.prof, P.start, P.end, P.streak, P.Kr
    bx0, by0, bx1, by1 = P.bbox
    if cov is None:
        cov = np.zeros((by1 - by0, bx1 - bx0), np.float32)  # max coverage so far in this stroke
    D, res_out, res = P.D, res, res if res_in else None
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
                 * _ss((al + ALONG[tip] * P.r0 - start[idx] * P.r0) / ew)
                 * _ss((P.length + ALONG[tip] * P.rl - end[idx] * P.rl - al) / ew) * prof[idx])
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
    if res_out is not None and res is not None and res is not res_out:
        res_out[...] = res
    return Coverage(cov, P.bbox)
