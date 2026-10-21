"""H8 package B: the native stamper against the numpy brush engine, byte for byte, and how long each takes.

    set PYTHONPATH=<patched kit>;<original kit's parent, as package rp_orig>;shared\\core
    set ROSTRUM_STAMP_LIB=apps\\2d\\engine\\target\\agent\\rostrum2d_stamp.dll
    .venv\\Scripts\\python.exe proofs\\2d-native-stamp\\judge.py <out.json>

Same strokes, three ways, on the same starting layer: the kit as it is on main (`rp_orig`), the patched kit's numpy
dabs, the patched kit with the native stamper. Every layer and every coverage must be identical, bytes and all.
"""
import json
import sys
import time

import numpy as np

import rp_orig.brush as OB
from rostrum_paint import brush as B, compose, marks, native

H, W = 200, 320


def strokes():
    """Every tip in every mode, wet, picking up, grain, a mask, off the edge, a dot, a fixed angle, jitter, pressure."""
    out = []
    for k, tip in enumerate(marks.TIPS):
        for m, mode in enumerate(marks.MODES):
            y = 20 + 30 * m + 3 * k
            pts = [[10 + 50 * k, y, 0.3], [60 + 50 * k, y + 12, 1.0], [120 + 45 * k, y - 6, 0.6]]
            out.append(dict(points=pts, color=(0.8, 0.3 + 0.1 * m, 0.2), size=6 + 5 * k, brush=tip, mode=mode,
                            seed=k * 7 + m, hardness=0.3 + 0.1 * m))
    for k, tip in enumerate(marks.TIPS):
        pts = [[30 + 40 * k, 30], [60 + 40 * k, 120, 0.5], [20 + 40 * k, 190, 0.9]]
        out.append(dict(points=pts, color=(0.1, 0.5, 0.9), size=18, brush=tip, wet=0.3 + 0.1 * k, seed=40 + k))
        out.append(dict(points=pts, color=(0.9, 0.9, 0.2), size=14, brush=tip, wet=0.7, sample_all=True,
                        seed=50 + k, mode="normal" if k % 2 else "multiply"))
        out.append(dict(points=pts[::-1], color=(0.4, 0.2, 0.6), size=22, brush=tip, grain=0.5, seed=60 + k,
                        hue_jitter=20, color_jitter=0.2, jitter=0.15, _mask=True))
    out += [dict(points=[[-20, -10], [40, 30], [330, 210]], color=(1, 0, 0), size=30, brush="bristle", wet=0.5,
                 sample_all=True, seed=1),                                         # off both edges, wet
            dict(points=[[100, 100]], color=(0, 1, 0), size=12, brush="round", seed=2),          # a dot
            dict(points=[[50, 50], [250, 150]], color=(0, 0, 1), size=16, brush="flat", angle=30, seed=3),
            dict(points=[[0, 199], [319, 0]], color=(1, 1, 1), size=40, brush="block", opacity=0.6, seed=4),
            dict(points=[[10, 10], [300, 15]], color=(0.5, 0.5, 0.5), size=0.6, brush="line", seed=5)]
    return out


def mask():
    return compose.mask_array({"points": [[40, 20], [300, 40], [200, 190], [20, 150]], "feather": 3,
                               "invert": False}, W, H)


def run(stamp, layer, s, under, paper):
    s = dict(s)
    m = mask() if s.pop("_mask", False) else None
    cov = stamp(layer, s.pop("points"), s.pop("color"), s.pop("size"), s.pop("brush"), mask=m,
                under=under if s.get("sample_all") else None, paper=paper, **s)
    return None if cov is None else (cov.a.tobytes(), cov.bbox)


def judge():
    """Each stroke onto the same evolving layer three ways; the first difference fails loudly."""
    rng = np.random.default_rng(0)
    base = (rng.random((H, W, 4)) * 0.6).astype(np.float32)
    base[..., :3] = np.minimum(base[..., :3], base[..., 3:])                 # premultiplied
    under = np.ascontiguousarray(np.concatenate([rng.random((H, W, 3)), np.ones((H, W, 1))], 2), np.float32)[..., :3]
    paper = marks.Paper(H, W, 0, 3.0)
    ways = {"main": OB.stamp_stroke, "numpy": B.stamp_stroke,
            "native": lambda *a, **k: B.stamp_stroke(*a, lay=native.lay, **k)}
    layers = {k: base.copy() for k in ways}
    for n, s in enumerate(strokes()):
        got = {k: run(f, layers[k], s, under, paper) for k, f in ways.items()}
        for k in ("numpy", "native"):
            if got[k] != got["main"] or layers[k].tobytes() != layers["main"].tobytes():
                d = np.abs(layers[k] - layers["main"])
                raise SystemExit(f"stroke {n} ({s['brush']}, {s.get('mode', 'normal')}, wet {s.get('wet', 0)}): {k} "
                                 f"differs from main: coverage {'same' if got[k] == got['main'] else 'differs'}, "
                                 f"layer max diff {d.max()} at {np.unravel_index(d.argmax(), d.shape)}")
    return {"strokes": len(strokes()), "identical": True, "layerBytes": layers["main"].nbytes}


def bench():
    """20-stroke bristle batches (8–40 px; short pen strokes, long sweeps, long wet ones) on a 1080p layer: stamping
    time, numpy vs native."""
    Hb, Wb = 1080, 1920
    paper = marks.Paper(Hb, Wb, 0, 3.0)
    under = np.zeros((Hb, Wb, 4), np.float32)[..., :3]
    def batch(wet, short=False):
        r = np.random.default_rng(7 if wet else 3)
        def path():
            if short:                                         # a pen stroke: ~250 px, three points
                x, y = r.uniform(200, 1700), r.uniform(200, 900)
                return [[x + 120 * k, y + r.uniform(-60, 60)] for k in range(3)]
            return [[float(x), float(y)] for x, y in zip(r.uniform(100, 1800, 6), r.uniform(100, 1000, 6))]
        return [dict(points=[[x, y, 0.5 + 0.5 * r.random()] for x, y in path()],
                     color=tuple(r.random(3)), size=float(r.uniform(8, 40)), brush="bristle", seed=i,
                     **(dict(wet=0.6, sample_all=bool(i % 2)) if wet else {})) for i in range(20)]
    out = {}
    for name, wet, short in (("20 short bristle strokes, 8-40 px, ~250 px long", False, True),
                             ("20 long bristle sweeps, 8-40 px, ~3,500 px long", False, False),
                             ("20 long wet bristle sweeps (smudge, half picking up)", True, False)):
        row = {}
        for way, lay in (("numpy", None), ("native", native.lay)):
            layer = np.zeros((Hb, Wb, 4), np.float32)
            t0 = time.perf_counter()
            for s in batch(wet, short):
                run(lambda *a, **k: B.stamp_stroke(*a, lay=lay, **k), layer, s, under, paper)
            row[way + "S"] = round(time.perf_counter() - t0, 3)
            row[way + "Sha1"] = __import__("hashlib").sha1(layer.tobytes()).hexdigest()
        row["sameBytes"] = row["numpySha1"] == row["nativeSha1"]
        row["speedup"] = round(row["numpyS"] / row["nativeS"], 1)
        out[name] = row
    return out


if __name__ == "__main__":
    native._lib()
    report = {"judge": judge(), "bench": bench()}
    open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
