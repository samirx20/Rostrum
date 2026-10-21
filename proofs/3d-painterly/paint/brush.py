"""A small brush engine agents paint textures with (Rostrum painterly proof).

Canvas values are sRGB-encoded floats 0..1: a texture painted by eye, not linear light.
Every stroke is plain data in `canvas.log`, so a painting replays exactly.
"""
import colorsys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

TIPS = ("round", "bristle", "chalk", "flat")
K = 64  # samples across the tip for per-bristle profiles
ALONG = {"round": 1.0, "chalk": 1.0, "bristle": 0.4, "flat": 0.3}  # tip length along the stroke / width


def _ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _noise(h, w, cell, rng):
    """Smooth value noise 0..1 with features about `cell` pixels wide."""
    g = rng.random((int(h / cell) + 3, int(w / cell) + 3)).astype(np.float32)
    return np.asarray(Image.fromarray(g, "F").resize((w, h), Image.BICUBIC)).clip(0, 1)


def _noise1(n, cell, rng):
    knots = rng.random(int(n / cell) + 2)
    return np.interp(np.linspace(0, len(knots) - 1, n), np.arange(len(knots)), knots)


def curve(*pts, n=32, pressure=(1.0, 1.0, 1.0)):
    """Smooth line through the given (x, y) points; pressure eases start -> mid -> end."""
    P = np.array([p[:2] for p in pts], float)
    if len(P) < 2:
        raise ValueError("curve needs at least two points")
    Q = np.vstack([P[0], P, P[-1]])
    segs = len(P) - 1
    t = np.linspace(0, segs, n)
    i = np.minimum(t.astype(int), segs - 1)
    f = (t - i)[:, None]
    p0, p1, p2, p3 = Q[i], Q[i + 1], Q[i + 2], Q[i + 3]
    xy = 0.5 * (2 * p1 + (p2 - p0) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f ** 2
                + (3 * p1 - p0 - 3 * p2 + p3) * f ** 3)
    u = np.linspace(0, 1, n)
    s, m, e = pressure
    pr = np.where(u < 0.5, s + (m - s) * _ss(u * 2), m + (e - m) * _ss(u * 2 - 1))
    return [(float(x), float(y), float(p)) for (x, y), p in zip(xy, pr)]


class Mask:
    """A region paint stays inside. `spec` is plain data so strokes using it replay."""
    def __init__(self, spec, a):
        self.spec, self.a = spec, a

    def inverted(self):
        return Mask({**self.spec, "invert": not self.spec.get("invert", False)}, 1 - self.a)


class Canvas:
    def __init__(self, w, h, fill=(1.0, 1.0, 1.0), grain_seed=0, grain_size=3.0):
        self.w, self.h = int(w), int(h)
        self.img = np.empty((self.h, self.w, 3), np.float32)
        self.img[:] = np.asarray(fill, np.float32)
        self.base = None
        self.head = dict(w=self.w, h=self.h, fill=list(fill), grain_seed=grain_seed, grain_size=grain_size)
        self.log, self._grain, self._fine = [], None, None

    @classmethod
    def load(cls, path, **kw):
        a = np.asarray(Image.open(path).convert("RGB"), np.float32) / 255
        c = cls(a.shape[1], a.shape[0], **kw)
        c.img[:] = a
        c.base = str(path)
        return c

    def save(self, path):
        Image.fromarray((self.img.clip(0, 1) * 255 + 0.5).astype(np.uint8)).save(path)

    def save_log(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({**self.head, "base": self.base, "ops": self.log}, f)

    @classmethod
    def replay(cls, log_path):
        with open(log_path, encoding="utf-8") as f:
            d = json.load(f)
        kw = dict(grain_seed=d["grain_seed"], grain_size=d["grain_size"])
        c = cls.load(d["base"], **kw) if d.get("base") else cls(d["w"], d["h"], d["fill"], **kw)
        for op in d["ops"]:
            args = {k: v for k, v in op.items() if k != "op"}
            if args.get("mask"):
                args["mask"] = c._mask(args["mask"])
            c.stroke(**args)
        return c

    # --- masks and textures --------------------------------------------------
    def mask_from_polygon(self, points, feather=0.0):
        return self._mask({"polygon": [[float(x), float(y)] for x, y, *_ in points], "feather": feather})

    def _mask(self, spec):
        im = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(im).polygon([tuple(p) for p in spec["polygon"]], fill=255)
        if spec.get("feather"):
            im = im.filter(ImageFilter.GaussianBlur(spec["feather"]))
        a = np.asarray(im, np.float32) / 255
        return Mask(spec, 1 - a if spec.get("invert") else a)

    def grain_field(self):
        """Paper/canvas tooth 0..1 (low = valley where thin paint breaks)."""
        if self._grain is None:
            rng, s = np.random.default_rng(self.head["grain_seed"]), self.head["grain_size"]
            self._grain = 0.6 * _noise(self.h, self.w, s, rng) + 0.4 * _noise(self.h, self.w, s * 4, rng)
            self._fine = _noise(self.h, self.w, 1.5, rng)
        return self._grain

    # --- strokes ---------------------------------------------------------------
    def stroke(self, points, color, size, opacity=1.0, tip="round", hardness=0.5, spacing=0.1,
               jitter=0.0, seed=0, angle=None, wet=0.0, grain=0.0, mode="normal", mask=None,
               color_jitter=0.04, size_pressure=0.8, opacity_pressure=0.3):
        if tip not in TIPS or mode not in ("normal", "multiply"):
            raise ValueError(f"tip must be one of {TIPS}, mode 'normal' or 'multiply'")
        if mask is not None and not isinstance(mask, Mask):
            raise TypeError("mask must come from canvas.mask_from_polygon (so the stroke can replay)")
        pts = np.array([(p[0], p[1], p[2] if len(p) > 2 else 1.0) for p in points], float)
        self.log.append(dict(op="stroke", points=pts.tolist(), color=list(map(float, color)), size=size,
                             opacity=opacity, tip=tip, hardness=hardness, spacing=spacing, jitter=jitter,
                             seed=seed, angle=angle, wet=wet, grain=grain, mode=mode, color_jitter=color_jitter,
                             size_pressure=size_pressure, opacity_pressure=opacity_pressure,
                             mask=mask.spec if mask else None))
        rng = np.random.default_rng(seed)
        # resample the path: one stamp every spacing * (local tip length) pixels
        seg = np.hypot(*np.diff(pts[:, :2], axis=0).T) if len(pts) > 1 else np.zeros(0)
        L = np.concatenate([[0], np.cumsum(seg)])
        step = max(0.5, spacing * size * ALONG[tip] * (0.6 if wet > 0 else 2))  # smudge needs dense stamps
        t = [0.0]
        while t[-1] < L[-1]:
            p = np.interp(t[-1], L, pts[:, 2])
            t.append(t[-1] + max(0.5, step * (1 - size_pressure * (1 - p))))
        t = np.minimum(np.array(t), L[-1])
        X, Y, Pr = (np.interp(t, L, pts[:, k]) if L[-1] > 0 else pts[:1, k] for k in range(3))
        S = t / L[-1] if L[-1] > 0 else np.zeros(1)
        n = len(t)
        if angle is None:
            th = np.arctan2(np.gradient(Y), np.gradient(X)) if n > 1 else np.zeros(1)
        else:
            th = np.full(n, math.radians(angle))
        X = X + rng.normal(0, jitter * size, n)
        Y = Y + rng.normal(0, jitter * size, n)
        # per-stroke tip profile across the brush: bristles, ragged start/end, colour streaks
        v = np.linspace(-1, 1, K)
        if tip == "bristle":
            nb = int(np.clip(size / 2, 10, 60))
            prof = np.zeros(K)
            for c, w_, s_ in zip(rng.uniform(-.95, .95, nb), rng.uniform(.04, .1, nb), rng.uniform(.4, 1, nb)):
                prof = np.maximum(prof, s_ * np.exp(-((v - c) / w_) ** 2))
            prof = 0.7 * prof + 0.3 * _noise1(K, 8, rng)
        elif tip == "flat":
            prof = 0.75 + 0.25 * _noise1(K, 4, rng)
        else:
            prof = np.ones(K)
        rag = {"bristle": (0.12, 0.35, 1.5), "flat": (0.08, 0.2, 5)}.get(tip, (0, 0, 8))
        start = rag[0] * _noise1(K, rag[2], rng)
        end = 1 - rag[1] * _noise1(K, rag[2], rng)
        streak = (_noise1(K, 2 if tip == "bristle" else 6, rng) - 0.5) * 2
        hn, sn, vn = ((_noise1(n, max(2, size / step), rng) - 0.5) * 2 for _ in range(3))
        base = colorsys.rgb_to_hsv(*np.clip(color, 0, 1))
        cols = [colorsys.hsv_to_rgb((base[0] + color_jitter * 0.5 * a) % 1, np.clip(base[1] * (1 + color_jitter * b), 0, 1),
                                    np.clip(base[2] * (1 + color_jitter * c), 0, 1)) for a, b, c in zip(hn, sn, vn)]
        G = self.grain_field() if grain > 0 or tip == "chalk" else None
        soft = max(1 - hardness, 0.03)
        R = (size / 2) * (1 - size_pressure * (1 - Pr))
        A = opacity * (1 - opacity_pressure * (1 - Pr))
        bx0 = int(max(0, np.floor((X - R).min()) - 1)); bx1 = int(min(self.w, np.ceil((X + R).max()) + 2))
        by0 = int(max(0, np.floor((Y - R).min()) - 1)); by1 = int(min(self.h, np.ceil((Y + R).max()) + 2))
        if bx1 <= bx0 or by1 <= by0:
            return
        cov = np.zeros((by1 - by0, bx1 - bx0), np.float32)  # max coverage so far in this stroke
        D, res = int(2 * R.max()) + 6, None
        for i in range(n):
            r = R[i]
            if r < 0.3:
                continue
            x0, x1 = max(bx0, int(X[i] - r) - 1), min(bx1, int(X[i] + r) + 2)
            y0, y1 = max(by0, int(Y[i] - r) - 1), min(by1, int(Y[i] + r) + 2)
            if x1 <= x0 or y1 <= y0:
                continue
            dx = (np.arange(x0, x1, dtype=np.float32) - X[i])[None, :]
            dy = (np.arange(y0, y1, dtype=np.float32) - Y[i])[:, None]
            c, s = math.cos(th[i]), math.sin(th[i])
            u, vv = (dx * c + dy * s) / r, (dy * c - dx * s) / r
            idx = ((np.clip(vv, -1, 1) + 1) * (K - 1) / 2).astype(np.int32)
            if tip in ("round", "chalk"):
                a = _ss((1 - np.sqrt(u * u + vv * vv)) / soft)
                if tip == "chalk":
                    a = _ss((a - 0.85 * (1 - self._fine[y0:y1, x0:x1])) / 0.3)
            elif tip == "bristle":
                a = _ss((1 - (u / ALONG[tip]) ** 2 - vv * vv) / soft)
            else:
                a = _ss((1 - np.abs(u) / ALONG[tip]) / soft) * _ss((1 - np.abs(vv)) / (soft * 0.3))
            if tip in ("bristle", "flat"):
                a = a * (prof * _ss((S[i] - start) / 0.06) * _ss((end - S[i]) / 0.06))[idx]
            a = a * A[i]
            if G is not None and grain > 0:
                tg = grain * (1 - G[y0:y1, x0:x1])
                a = np.clip((a - tg) / (1.001 - tg), 0, 1)
            if mask is not None:
                a = a * mask.a[y0:y1, x0:x1]
            cv = cov[y0 - by0:y1 - by0, x0 - bx0:x1 - bx0]
            c1 = np.maximum(cv, a)
            inc = ((c1 - cv) / (1.0001 - cv))[..., None]
            cv[...] = c1
            col = np.asarray(cols[i], np.float32) * (1 + color_jitter * 0.6 * streak[idx])[..., None]
            region = self.img[y0:y1, x0:x1]
            if wet > 0:  # smudge: the brush carries a reservoir of the paint it passed over
                oy, ox = int(round(Y[i])) - D // 2, int(round(X[i])) - D // 2
                win = (slice(y0 - oy, y1 - oy), slice(x0 - ox, x1 - ox))
                under = self.img[np.ix_(np.clip(np.arange(oy, oy + D), 0, self.h - 1),
                                        np.clip(np.arange(ox, ox + D), 0, self.w - 1))]
                if res is None:
                    res = under
                lt = math.hypot(X[i] - X[i - 1], Y[i] - Y[i - 1]) / (2 * r * ALONG[tip]) if i else 0
                region += (a * (1 - (1 - 0.97 * wet) ** max(lt, 0.05)))[..., None] * (res[win] - region)
                res += (1 - (0.6 * wet) ** max(lt, 0.05)) * (under - res)
            inc = inc * (1 - wet)
            if mode == "multiply":
                region *= 1 - inc * (1 - col)
            else:
                region += inc * (col - region)

    def fill_region(self, mask, color, size, angle=0.0, gap=0.7, length=4.0, bend=0.15,
                    pressure=(0.5, 1.0, 0.3), seed=0, **stroke_kw):
        """Block-in tool: hatch the mask's area with many strokes running at `angle` degrees."""
        rng = np.random.default_rng(seed)
        ys, xs = np.nonzero(mask.a > 0.5)
        if not len(xs):
            raise ValueError("fill_region: the mask is empty")
        cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        rad = math.hypot(xs.max() - xs.min(), ys.max() - ys.min()) / 2 + size
        d = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
        nrm = np.array([-d[1], d[0]])
        for off in np.arange(-rad, rad, gap * size):
            t = -rad - rng.uniform(0, length * size)
            while t < rad:
                ln = length * size * rng.uniform(0.7, 1.3)
                o = off + rng.normal(0, 0.15 * gap * size)
                p0, p2 = np.array([cx, cy]) + d * t + nrm * o, np.array([cx, cy]) + d * (t + ln) + nrm * o
                p1 = (p0 + p2) / 2 + nrm * ln * bend * rng.normal()
                mx, my = int(p1[0]), int(p1[1])
                if 0 <= mx < self.w and 0 <= my < self.h and mask.a[my, mx] > 0.5:
                    self.stroke(curve(p0, p1, p2, n=12, pressure=pressure), color, size, mask=mask,
                                seed=int(rng.integers(1 << 30)), **stroke_kw)
                t += ln * rng.uniform(0.6, 0.9)
