"""Bowl albedo (2048): unglazed terracotta outside, ochre/cream slip glaze inside, glaze drips over the rim.

UV (from guides/bowl_guide.png): image y = (1 - v) * 2048; u = x / 2048, camera sees u 0.3-0.7 (x 614-1434).
  inside floor centre v=1 (y 0) | inside wall 0.73 (y 553) | rim 0.52 (y 983) | outside wall 0.42 (y 1188)
  foot 0.15 (y 1741) | underside v<0.15.
On screen u is ~1 texel per pixel but v is squashed ~4x, so vertical marks need width to read.
Run: uv run --with numpy --with pillow python -I paint_bowl.py
"""
import sys
import time
import numpy as np

PAINT = r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint"
sys.path.insert(0, PAINT)
from brush import Canvas, curve  # noqa: E402

W = 2048
OUT = PAINT + r"\textures"
rng = np.random.default_rng(11)
seed = iter(range(1, 100000))


def Y(v):
    return (1.0 - v) * W


CLAY = [(0.71, 0.39, 0.24), (0.76, 0.46, 0.30), (0.62, 0.32, 0.21), (0.68, 0.40, 0.28), (0.74, 0.42, 0.24)]
GLAZE = [(0.88, 0.73, 0.42), (0.92, 0.83, 0.60), (0.84, 0.66, 0.35), (0.90, 0.78, 0.50), (0.94, 0.87, 0.68)]
POOL = [(0.74, 0.52, 0.25), (0.70, 0.48, 0.24), (0.78, 0.58, 0.30)]


def around(c, y0, y1, colors, size, rows, tip="bristle", tilt=10, ln=(260, 480), opacity=0.9, **kw):
    """Strokes running around the bowl (horizontal in UV), covering y0..y1."""
    for r in range(rows):
        y = y0 + (y1 - y0) * (r + rng.uniform(0.2, 0.8)) / rows
        x = -100 + rng.uniform(0, 160)
        while x < W + 100:
            L = rng.uniform(*ln)
            col = colors[rng.integers(len(colors))]
            c.stroke(curve((x, y), (x + L / 2, y + rng.normal(0, tilt)), (x + L, y + rng.normal(0, tilt * 0.6)),
                           pressure=(0.4, 1.0, 0.25)),
                     col, size * rng.uniform(0.8, 1.2), opacity=opacity, tip=tip, seed=next(seed), **kw)
            x += L * rng.uniform(0.55, 0.85)


def paint():
    c = Canvas(W, W, fill=CLAY[0], grain_seed=5, grain_size=3.5)
    # 1. Outside: terracotta block-in around the wall, then bolder form strokes.
    around(c, Y(0.53), W + 30, CLAY, 70, 22, color_jitter=0.07, grain=0.45)
    for _ in range(180):
        y = rng.uniform(Y(0.50), Y(0.14))
        x = rng.uniform(450, 1600)
        L = rng.uniform(180, 420)
        col = [(0.80, 0.52, 0.36), (0.58, 0.30, 0.20), (0.73, 0.44, 0.31), (0.66, 0.42, 0.33),
               (0.79, 0.47, 0.26)][rng.integers(5)]
        c.stroke(curve((x, y), (x + L / 2, y + rng.normal(0, 12)), (x + L, y + rng.normal(0, 8)),
                       pressure=(0.3, 1.0, 0.15)), col, rng.uniform(36, 70), opacity=rng.uniform(0.6, 0.9),
                 tip=["flat", "bristle", "chalk"][rng.integers(3)], seed=next(seed), color_jitter=0.08,
                 grain=0.5, wet=0.2 if rng.random() < 0.25 else 0.0)
    # Throwing rings: long strokes round the wall in alternating darker and lighter bands, with real value
    # steps (v is squashed ~4x on screen, so each ring needs 30-60 texels of height to read).
    yy = Y(0.50)
    k = 0
    while yy < Y(0.17):
        h = rng.uniform(34, 70)
        dark = k % 2 == 0
        col = [(0.56, 0.28, 0.18), (0.60, 0.31, 0.20)] if dark else [(0.84, 0.56, 0.40), (0.80, 0.52, 0.36)]
        around(c, yy + h * 0.5, yy + h * 0.5 + 1, col, h * 0.8, 1, tip="flat", tilt=3, ln=(380, 760),
               opacity=rng.uniform(0.75, 0.95), color_jitter=0.04, grain=0.5, size_pressure=0.3)
        yy += h * rng.uniform(1.0, 1.6)
        k += 1
    # A few lighter and darker passages across the rings (one side scorched darker, a dusty pale patch).
    for (cx, cy, col, n) in ((820, Y(0.33), (0.50, 0.25, 0.16), 6), (1300, Y(0.28), (0.88, 0.62, 0.46), 5),
                             (1050, Y(0.42), (0.86, 0.60, 0.44), 4), (640, Y(0.24), (0.52, 0.27, 0.17), 4)):
        for _ in range(n):
            x = rng.normal(cx, 80)
            y = rng.normal(cy, 40)
            L = rng.uniform(200, 380)
            c.stroke(curve((x - L / 2, y), (x, y + rng.normal(0, 6)), (x + L / 2, y + rng.normal(0, 6)),
                           pressure=(0.4, 1.0, 0.3)), col, rng.uniform(40, 70), opacity=rng.uniform(0.5, 0.75),
                     tip="chalk", seed=next(seed), color_jitter=0.05, grain=0.55)
    # Foot: rougher, darker raw clay with dusty chalk marks.
    around(c, Y(0.17), Y(0.10), [(0.56, 0.32, 0.22), (0.62, 0.38, 0.27)], 50, 3, tip="chalk",
           opacity=0.85, color_jitter=0.08, grain=0.6)
    # 2. Inside: slip glaze, cream near the rim, deepening to amber where it pools on the floor.
    inside = c.mask_from_polygon([(-40, -40), (W + 40, -40), (W + 40, Y(0.515)), (-40, Y(0.515))])
    around(c, -60, Y(0.515), [GLAZE[0], GLAZE[3]], 90, 30, tip="round", hardness=0.4, tilt=4, opacity=1.0,
           mask=inside, size_pressure=0.0, color_jitter=0.04)  # solid glaze ground so no clay shows through
    around(c, -40, Y(0.505), GLAZE, 80, 18, color_jitter=0.06, grain=0.25)
    around(c, -40, Y(0.86), POOL + [GLAZE[2]], 90, 6, opacity=0.75, color_jitter=0.06, grain=0.2, wet=0.15)
    for _ in range(160):  # form strokes on the inside wall
        y = rng.uniform(Y(0.95), Y(0.53))
        x = rng.uniform(450, 1600)
        L = rng.uniform(180, 400)
        col = (GLAZE + [(0.97, 0.91, 0.74), (0.80, 0.62, 0.34)])[rng.integers(7)]
        c.stroke(curve((x, y), (x + L / 2, y + rng.normal(0, 14)), (x + L, y + rng.normal(0, 8)),
                       pressure=(0.3, 1.0, 0.15)), col, rng.uniform(34, 66), opacity=rng.uniform(0.6, 0.9),
                 tip=["flat", "bristle"][rng.integers(2)], seed=next(seed), color_jitter=0.07, grain=0.35,
                 wet=0.25 if rng.random() < 0.3 else 0.0)
    # Glaze running down the inside wall toward the floor (upward in UV), darker where it is thick.
    for _ in range(22):
        x = rng.uniform(300, 1750)
        y0 = Y(0.53) - rng.uniform(0, 60)
        L = rng.uniform(120, 380)
        c.stroke(curve((x, y0), (x + rng.normal(0, 12), y0 - L / 2), (x + rng.normal(0, 18), y0 - L),
                       pressure=(0.5, 1.0, 0.6)), POOL[rng.integers(3)], rng.uniform(34, 60),
                 opacity=rng.uniform(0.15, 0.3), tip="round", hardness=0.35, mode="multiply", seed=next(seed),
                 color_jitter=0.06, grain=0.3)
    # Trailed brown slip line, wavy, round the inside wall.
    for k in range(2):
        yb = Y(0.62 + 0.045 * k)
        x = -60
        while x < W + 60:
            L = rng.uniform(150, 260)
            c.stroke(curve((x, yb + 14 * np.sin(x / 70)), (x + L / 2, yb + 14 * np.sin((x + L / 2) / 70)),
                           (x + L, yb + 14 * np.sin((x + L) / 70)), pressure=(0.6, 1.0, 0.6)),
                     (0.42, 0.24, 0.13), 18 - 4 * k, opacity=0.8, tip="round", hardness=0.6, seed=next(seed),
                     color_jitter=0.08, grain=0.35, size_pressure=0.5)
            x += L * 0.9
    # 3. Rim: glaze wraps over the rim and stops in a wavy edge on the outside, thinning to show clay.
    edge = [(x, Y(0.49) + 22 * np.sin(x / 113.0) + 10 * np.sin(x / 37.0)) for x in range(-40, W + 80, 40)]
    over = c.mask_from_polygon([(-40, Y(0.53))] + edge + [(W + 80, Y(0.53))], feather=3)
    around(c, Y(0.535), Y(0.47), GLAZE[:2] + GLAZE[3:], 40, 5, tip="flat", tilt=4, opacity=1.0, mask=over,
           color_jitter=0.07, grain=0.2)
    around(c, Y(0.527), Y(0.513), [(0.80, 0.56, 0.34), (0.86, 0.66, 0.42)], 18, 2, tip="chalk",
           tilt=3, opacity=0.6, color_jitter=0.08, grain=0.6)  # glaze breaking thin on the rim edge
    # Drips over the outside wall: clustered and irregular, varied width, a few running far down the wall.
    xs = list(rng.uniform(80, 1950, 6)) + list(rng.normal(820, 60, 4)) + list(rng.normal(1250, 90, 5))
    xs += [700, 1010, 1380]  # long runners in the camera's view
    for i, x in enumerate(xs):
        y0 = Y(0.49) + 22 * np.sin(x / 113.0) + 10 * np.sin(x / 37.0) - 14
        runner = i >= len(xs) - 3
        L = rng.uniform(380, 620) if runner else rng.choice([rng.uniform(20, 70), rng.uniform(80, 260)])
        wdt = rng.uniform(16, 60)
        col = [(0.88, 0.68, 0.40), (0.84, 0.62, 0.36), (0.90, 0.74, 0.48)][rng.integers(3)]  # glaze thin over clay
        dx = rng.normal(0, 14) * min(1.0, L / 200)  # short drips run straight, long ones wander
        c.stroke(curve((x, y0 - 10), (x + dx * 0.4 + rng.normal(0, 6), y0 + L * 0.5), (x + dx, y0 + L),
                       pressure=(1.0, rng.uniform(0.35, 0.7), 0.85)), col, wdt * 1.2, opacity=0.88, tip="round",
                 hardness=0.45, seed=next(seed), color_jitter=0.08, grain=0.3, size_pressure=0.6)
        c.stroke(curve((x + dx, y0 + L - wdt * 0.3), (x + dx, y0 + L - wdt * 0.1), (x + dx + 1, y0 + L)),
                 POOL[rng.integers(3)], wdt * 0.7, opacity=0.35, tip="round", hardness=0.3, mode="multiply",
                 seed=next(seed))  # glaze gathers thicker and darker at the drip end
    return c


if __name__ == "__main__":
    t = time.time()
    c = paint()
    c.save(OUT + r"\bowl.png"); c.save_log(OUT + r"\bowl.json")
    print(f"bowl albedo: {len(c.log)} strokes in {time.time() - t:.1f}s")
