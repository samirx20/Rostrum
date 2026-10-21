"""Pear albedo (1024): yellow-green skin, red-orange blush on one side, russet speckles and top patch, stem.

UV (from guides/pear_guide.png): image y = (1 - v) * 1024; u = x / 1024, front u=0.5 (x 512).
  bottom v=0 (y 1024) | widest 0.35 (y 666) | neck 0.67 (y 338) | top 0.90 (y 102) | stem strip v>0.92 (y<82).
Run: uv run --with numpy --with pillow python -I paint_pear.py
"""
import sys
import time
import numpy as np

PAINT = r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint"
sys.path.insert(0, PAINT)
from brush import Canvas, curve  # noqa: E402

W = 1024
OUT = PAINT + r"\textures"
rng = np.random.default_rng(23)
seed = iter(range(1, 100000))


def Y(v):
    return (1.0 - v) * W


SKIN = [(0.74, 0.75, 0.31), (0.82, 0.79, 0.36), (0.62, 0.66, 0.26), (0.78, 0.72, 0.30), (0.68, 0.72, 0.34)]
BLUSH = [(0.82, 0.34, 0.14), (0.72, 0.24, 0.12), (0.88, 0.48, 0.18)]
GREEN = [(0.55, 0.64, 0.24), (0.62, 0.68, 0.28), (0.50, 0.58, 0.22)]
YELLOW = [(0.86, 0.80, 0.34), (0.80, 0.78, 0.32), (0.90, 0.84, 0.42)]
OCHRE = [(0.80, 0.64, 0.26), (0.76, 0.70, 0.30), (0.84, 0.72, 0.34)]
RUSSET = [(0.55, 0.38, 0.19), (0.48, 0.32, 0.16), (0.62, 0.45, 0.24)]


def paint():
    c = Canvas(W, W, fill=SKIN[0], grain_seed=6, grain_size=2.5)
    body = c.mask_from_polygon([(-20, Y(0.915)), (W + 20, Y(0.915)), (W + 20, W + 20), (-20, W + 20)])
    # 1. Skin block-in, strokes running along the pear (top to bottom), the way the form flows.
    c.fill_region(body, SKIN[0], 60, angle=90, gap=0.7, length=4, seed=next(seed), tip="flat",
                  color_jitter=0.05, grain=0.3, opacity=0.9)
    # Colour passages: each x band leans one way (green / yellow / ochre), so the steps read at frame size.
    ZONES = [(0, 160, GREEN), (160, 330, YELLOW), (330, 560, OCHRE), (560, 700, YELLOW), (700, 900, GREEN),
             (900, 1024, YELLOW)]
    for _ in range(150):
        x = rng.uniform(-30, W + 30)
        pal = next((p for a, b, p in ZONES if a <= x % W < b), YELLOW)
        if rng.random() < 0.2:
            pal = (GREEN, YELLOW, OCHRE)[rng.integers(3)]
        y0 = rng.uniform(Y(0.92), Y(0.25))
        L = rng.uniform(200, 420)
        c.stroke(curve((x, y0), (x + rng.normal(0, 12), y0 + L / 2), (x + rng.normal(0, 18), min(y0 + L, W + 20)),
                       pressure=(0.5, 1.0, 0.3)), pal[rng.integers(len(pal))], rng.uniform(40, 72),
                 opacity=rng.uniform(0.85, 1.0), tip=["flat", "bristle", "flat"][rng.integers(3)], seed=next(seed),
                 color_jitter=0.04, grain=0.35, mask=body, size_pressure=0.4)
    # Light accents along the length, where the skin turns to the light.
    for _ in range(18):
        x = rng.normal(560, 120)
        y0 = rng.uniform(Y(0.8), Y(0.35))
        L = rng.uniform(140, 300)
        c.stroke(curve((x, y0), (x + rng.normal(0, 8), y0 + L / 2), (x + rng.normal(0, 12), y0 + L),
                       pressure=(0.4, 1.0, 0.2)), (0.93, 0.88, 0.48), rng.uniform(26, 44), opacity=0.9,
                 tip="flat", seed=next(seed), color_jitter=0.04, grain=0.4, mask=body)
    # 2. Blush: broken red-orange strokes along the pear, strong in the heart, breaking up at the edges.
    for _ in range(70):
        x = rng.normal(400, 85)
        y0 = rng.uniform(Y(0.72), Y(0.15))
        L = rng.uniform(120, 300)
        core = abs(x - 400) < 70
        c.stroke(curve((x, y0), (x + rng.normal(0, 10), y0 + L / 2), (x + rng.normal(0, 16), y0 + L),
                       pressure=(0.5, 1.0, 0.2)), BLUSH[rng.integers(3)], rng.uniform(28, 56),
                 opacity=rng.uniform(0.75, 0.95) if core else rng.uniform(0.45, 0.7),
                 tip="bristle" if core else "chalk", seed=next(seed), color_jitter=0.05, grain=0.55, mask=body,
                 size_pressure=0.5)
    for _ in range(14):  # deep red streaks in the heart of the blush
        x = rng.normal(400, 40)
        y0 = rng.uniform(Y(0.6), Y(0.25))
        L = rng.uniform(100, 220)
        c.stroke(curve((x, y0), (x + rng.normal(0, 8), y0 + L / 2), (x + rng.normal(0, 10), y0 + L),
                       pressure=(0.4, 1.0, 0.2)), (0.66, 0.20, 0.10), rng.uniform(16, 30), opacity=0.85,
                 tip="bristle", seed=next(seed), color_jitter=0.05, grain=0.45, mask=body)
    # 3. Russet: a soft glaze round the top, then broken dry dabs in random directions, fading down.
    c.stroke(curve((-40, Y(0.88)), (W / 2, Y(0.875)), (W + 40, Y(0.88))), (0.78, 0.62, 0.42), 90,
             opacity=0.55, tip="chalk", mode="multiply", seed=next(seed), color_jitter=0.08, grain=0.6)
    for _ in range(260):
        y = Y(0.915) + abs(rng.normal(0, 60))
        x = rng.uniform(-20, W + 20)
        a0 = rng.uniform(0, 6.28)
        L = rng.uniform(10, 34)
        c.stroke(curve((x, y), (x + np.cos(a0) * L / 2, y + np.sin(a0) * L / 2), (x + np.cos(a0) * L, y + np.sin(a0) * L),
                       pressure=(0.5, 1.0, 0.4)), RUSSET[rng.integers(3)], rng.uniform(8, 20),
                 opacity=rng.uniform(0.45, 0.85), tip="chalk", seed=next(seed), color_jitter=0.1, grain=0.6)
    # Speckles (lenticels): fewer and bigger so they still read as dots at frame size.
    for _ in range(170):
        x = rng.uniform(0, W)
        y = Y(0.9) + (Y(0.02) - Y(0.9)) * rng.uniform(0, 1) ** 1.4
        s = rng.uniform(8, 15)
        c.stroke([(x, y), (x + s * 0.4, y + rng.normal(0, s * 0.2))], RUSSET[rng.integers(3)], s,
                 opacity=rng.uniform(0.5, 0.9), tip="chalk", seed=next(seed), color_jitter=0.08, grain=0.3)
    # Blossom end at the bottom: a dark russet ring.
    for _ in range(14):
        x = rng.uniform(-20, W)
        y = Y(0.03) + rng.normal(0, 8)
        c.stroke(curve((x, y), (x + 50, y + rng.normal(0, 6)), (x + 100, y + rng.normal(0, 6))),
                 (0.36, 0.25, 0.12), rng.uniform(14, 26), opacity=0.7, tip="chalk", seed=next(seed),
                 color_jitter=0.1, grain=0.5)
    # 4. Stem strip: brown, strokes along the stem (up in UV), a darker woody tip at the very top.
    stem = c.mask_from_polygon([(-20, -20), (W + 20, -20), (W + 20, Y(0.912)), (-20, Y(0.912))])
    for k in range(90):  # solid wood under the streaks
        x = -20 + k * 12
        c.stroke([(x, -10), (x, Y(0.905))], (0.40, 0.28, 0.15), 30, opacity=1.0, tip="round", hardness=0.6,
                 seed=next(seed), color_jitter=0.06, size_pressure=0.0, mask=stem)
    for k in range(60):
        x = -10 + k * (W + 20) / 60
        c.stroke(curve((x, Y(0.905)), (x + rng.normal(0, 4), Y(0.95)), (x + rng.normal(0, 6), -10),
                       pressure=(0.8, 1.0, 0.6)), [(0.42, 0.29, 0.15), (0.33, 0.24, 0.13), (0.50, 0.37, 0.20)][k % 3],
                 24, opacity=0.6, tip="bristle", seed=next(seed), color_jitter=0.1, grain=0.35, mask=stem)
    c.stroke(curve((-20, 12), (W / 2, 10), (W + 20, 14)), (0.20, 0.14, 0.09), 26, opacity=0.9, tip="chalk",
             seed=next(seed), mask=stem)
    return c


if __name__ == "__main__":
    t = time.time()
    c = paint()
    c.save(OUT + r"\pear.png"); c.save_log(OUT + r"\pear.json")
    print(f"pear albedo: {len(c.log)} strokes in {time.time() - t:.1f}s")
