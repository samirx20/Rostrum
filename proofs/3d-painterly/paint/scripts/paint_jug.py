"""Jug albedo (2048) + roughness (2048): cream enamel, cobalt rim band, base line, iron chips, warm staining.

UV (from guides/jug_guide.png): image y = (1 - v) * 2048; u = x / 2048, camera sees u 0.3-0.7 (x 614-1434).
  inside v>0.61 (y<799) | lip v=0.60 (y 819) | neck 0.56 | belly 0.40 (y 1229) | base edge 0.28 (y 1475)
  bottom 0.20 (y 1638) | handle strip v<0.18 (y>1679), u along the handle, v around it.
Run: uv run --with numpy --with pillow python -I paint_jug.py
"""
import sys
import time
import numpy as np

PAINT = r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint"
sys.path.insert(0, PAINT)
from brush import Canvas, curve  # noqa: E402

W = 2048
OUT = PAINT + r"\textures"


def Y(v):
    return (1.0 - v) * W


def shade(c, k):
    return tuple(min(1.0, max(0.0, x * k)) for x in c)


CREAM = (0.91, 0.88, 0.79)
INSIDE = (0.74, 0.70, 0.60)
COBALT = (0.10, 0.20, 0.52)
IRON = (0.13, 0.11, 0.10)
RUST = (0.48, 0.28, 0.14)

rng = np.random.default_rng(7)
seed = iter(range(1, 100000))

# Chips (shared by albedo and roughness): (x, y, radius)
CHIPS = [(700, 812, 16), (905, 806, 11), (1180, 818, 20), (1330, 809, 9), (1050, 830, 7),
         (820, 1470, 14), (1120, 1478, 18), (1390, 1466, 10), (960, 1462, 7)]


def band_strokes(c, y0, y1, colors, size, n_rows, tip="bristle", tilt=18, opacity=0.9, **kw):
    """Strokes running around the form (horizontal in UV) with a gentle sag, covering y0..y1."""
    for r in range(n_rows):
        y = y0 + (y1 - y0) * (r + rng.uniform(0.2, 0.8)) / n_rows
        x = -100 + rng.uniform(0, 160)
        while x < W + 100:
            ln = rng.uniform(220, 420)
            sag = rng.normal(0, tilt)
            col = colors[rng.integers(len(colors))]
            c.stroke(curve((x, y), (x + ln / 2, y + sag), (x + ln, y + rng.normal(0, tilt * 0.6)),
                           pressure=(0.4, 1.0, 0.25)),
                     col, size * rng.uniform(0.8, 1.2), opacity=opacity, tip=tip, seed=next(seed), **kw)
            x += ln * rng.uniform(0.55, 0.85)


def paint_albedo():
    c = Canvas(W, W, fill=CREAM, grain_seed=3, grain_size=3.0)
    # 1. Inside: darker cream, strokes around.
    band_strokes(c, -40, Y(0.605), [INSIDE, shade(INSIDE, 0.92), (0.79, 0.73, 0.59), (0.72, 0.69, 0.61)],
                 90, 12, color_jitter=0.06, grain=0.3)
    # 2. Body block-in: few wide passes of mid cream, strokes around the belly.
    body = [CREAM, (0.90, 0.86, 0.77), (0.92, 0.87, 0.74)]
    band_strokes(c, Y(0.585), Y(0.20) + 30, body, 120, 7, tip="flat", color_jitter=0.04, grain=0.3)
    # 3. Form strokes: fewer, wide and decisive, with clear value/colour steps. Warm cream and
    # cool grey-violet sit in separate passages (by x and height) instead of mixing into wisps.
    WARM = [(0.98, 0.92, 0.76), (0.99, 0.95, 0.86), (0.93, 0.83, 0.64)]
    COOL = [(0.78, 0.76, 0.82), (0.72, 0.71, 0.78), (0.83, 0.81, 0.83)]
    cool_x = [(560, 760), (1010, 1150), (1330, 1500)]  # cool passages; the rest leans warm
    for _ in range(110):
        v = rng.uniform(0.29, 0.575)
        y = Y(v)
        x = rng.uniform(450, 1600)
        ln = rng.uniform(220, 460)
        bulge = 1.0 - abs(v - 0.40) / 0.2  # 1 at the belly
        mid = x + ln / 2
        cool = any(a <= mid <= b for a, b in cool_x) or (v < 0.34 and rng.random() < 0.5)
        if rng.random() < 0.15:
            cool = not cool
        col = (COOL if cool else WARM)[rng.integers(3)]
        sag = (6 + 12 * max(bulge, 0)) * (1 if v < 0.40 else -1) + rng.normal(0, 6)
        c.stroke(curve((x, y), (x + ln / 2, y + sag), (x + ln, y + rng.normal(0, 8)), pressure=(0.5, 1.0, 0.3)),
                 col, rng.uniform(45, 92), opacity=rng.uniform(0.85, 1.0),
                 tip=["flat", "bristle", "flat"][rng.integers(3)], seed=next(seed), color_jitter=0.04,
                 grain=0.35, size_pressure=0.4)
    # A few bright warm accents on the shoulder to carry the light.
    for _ in range(10):
        y = Y(rng.uniform(0.47, 0.56))
        x = rng.uniform(780, 1300)
        ln = rng.uniform(160, 300)
        c.stroke(curve((x, y), (x + ln / 2, y - 6), (x + ln, y + rng.normal(0, 6)), pressure=(0.4, 1.0, 0.2)),
                 (1.0, 0.96, 0.84), rng.uniform(40, 70), opacity=0.95, tip="flat", seed=next(seed),
                 color_jitter=0.03, grain=0.3)
    # 4. Neck: a cooler, slightly greyer cream that pinches in under the rim.
    band_strokes(c, Y(0.575), Y(0.545), [(0.80, 0.78, 0.82), (0.86, 0.84, 0.82)], 60, 2,
                 tip="flat", opacity=0.8, color_jitter=0.04, grain=0.4)
    # 5. Warm staining: thin glazes running down from the rim and pooling at the base.
    for _ in range(26):
        x = rng.uniform(500, 1550)
        y0 = Y(0.578) + rng.uniform(0, 30)
        ln = rng.uniform(80, 340)
        c.stroke(curve((x, y0), (x + rng.normal(0, 10), y0 + ln / 2), (x + rng.normal(0, 16), y0 + ln),
                       pressure=(0.9, 0.6, 0.1)),
                 (0.86, 0.74, 0.52), rng.uniform(14, 34), opacity=rng.uniform(0.12, 0.28), tip="round",
                 hardness=0.3, mode="multiply", seed=next(seed), color_jitter=0.08, grain=0.5)
    band_strokes(c, Y(0.33), Y(0.285), [(0.88, 0.78, 0.60), (0.84, 0.76, 0.62)], 60, 2,
                 tip="chalk", opacity=0.22, mode="multiply", color_jitter=0.1, grain=0.6)
    # 6. Cobalt rim band at the lip (v 0.58-0.61), rolling over to the inside edge.
    blues = [COBALT, (0.08, 0.17, 0.46), (0.14, 0.26, 0.58), (0.11, 0.21, 0.50)]
    band_strokes(c, Y(0.622), Y(0.580), blues[:2], 66, 2, tip="flat", opacity=1.0, color_jitter=0.04,
                 grain=0.15, tilt=2)
    # Broken lower edge: a few longer dry drags that dip below the band and thin out.
    for _ in range(16):
        x = rng.uniform(-40, W + 40)
        y = Y(0.582) + rng.uniform(2, 12)
        ln = rng.uniform(60, 160)
        c.stroke(curve((x, y), (x + ln / 2, y + rng.uniform(2, 10)), (x + ln, y + rng.normal(0, 4)),
                       pressure=(0.6, 1.0, 0.1)), blues[rng.integers(2)], rng.uniform(14, 24),
                 opacity=0.9, tip="bristle", seed=next(seed), color_jitter=0.04, grain=0.55)
    # 7. Thin blue line just above the base edge.
    band_strokes(c, Y(0.293), Y(0.284), blues, 16, 1, tip="flat", opacity=0.9, color_jitter=0.06,
                 grain=0.35, tilt=3)
    # 8. Bottom (mostly unseen): grey-cream, quick.
    band_strokes(c, Y(0.278), Y(0.18), [(0.80, 0.78, 0.72), (0.76, 0.74, 0.70)], 80, 3, opacity=0.8,
                 color_jitter=0.05, grain=0.4)
    # 9. Handle strip: cream along the handle with two blue edge lines (v 0.045 and 0.135).
    c.fill_region(c.mask_from_polygon([(-20, Y(0.182)), (W + 20, Y(0.182)), (W + 20, W + 20), (-20, W + 20)]),
                  CREAM, 60, angle=0, gap=0.6, length=5, seed=next(seed), tip="bristle", color_jitter=0.06,
                  grain=0.35, opacity=0.9)
    for vv in (0.07, 0.11):  # lighter top of the handle tube, slightly warmer underside
        band_strokes(c, Y(vv + 0.02), Y(vv - 0.02), [(0.95, 0.92, 0.84), (0.90, 0.85, 0.74)], 44, 2,
                     tip="flat", opacity=0.6, color_jitter=0.06, grain=0.4, tilt=6)
    for vv in (0.045, 0.135):
        band_strokes(c, Y(vv + 0.006), Y(vv - 0.006), blues, 18, 1, tip="flat", opacity=0.92,
                     color_jitter=0.06, grain=0.3, tilt=3)
    # 10. Chips: a cluster of small irregular dabs - rusty halo, dark iron core, broken light enamel edge.
    for (x, y, r) in CHIPS:
        c.stroke(curve((x - r, y + r * 0.2), (x, y - r * 0.3), (x + r * 1.1, y + r * 0.1)), RUST, r * 1.6,
                 opacity=0.35, tip="chalk", mode="multiply", seed=next(seed), color_jitter=0.1, grain=0.6)
        c.stroke(curve((x - r * 0.9, y), (x, y + rng.normal(0, r * 0.3)), (x + r, y + rng.normal(0, r * 0.2))),
                 (0.84, 0.85, 0.84), r * 1.5, opacity=0.9, tip="chalk", seed=next(seed), color_jitter=0.05,
                 grain=0.3)  # pale ground coat showing round the iron
        for k in range(int(rng.integers(3, 6))):
            ox, oy = rng.normal(0, r * 0.5), rng.normal(0, r * 0.3)
            a0 = rng.uniform(0, 180)
            L = r * rng.uniform(0.5, 1.1)
            c.stroke(curve((x + ox, y + oy), (x + ox + L * 0.5, y + oy + rng.normal(0, r * 0.2)),
                           (x + ox + L, y + oy + rng.normal(0, r * 0.3)), pressure=(0.5, 1.0, 0.4)),
                     IRON if k else (0.22, 0.16, 0.12), r * rng.uniform(0.8, 1.25), opacity=0.95,
                     tip="flat", angle=a0, seed=next(seed), color_jitter=0.08, grain=0.2)
        for k in range(2):  # broken enamel edge catching light, only on part of the chip
            ox = rng.uniform(-r, r * 0.3)
            c.stroke(curve((x + ox, y - r * 0.55), (x + ox + r * 0.4, y - r * 0.7), (x + ox + r * 0.8, y - r * 0.5),
                           pressure=(0.2, 1.0, 0.2)), (0.98, 0.96, 0.90), max(3, r * 0.22), opacity=0.7,
                     tip="chalk", seed=next(seed))
    return c


def paint_rough():
    """Roughness as grey paint: enamel ~0.2 (value ~55), chips ~0.6 (~150), inside and base a bit rougher."""
    g = lambda k: (k / 255, k / 255, k / 255)  # noqa: E731
    c = Canvas(W, W, fill=g(55), grain_seed=4, grain_size=3.0)
    band_strokes(c, Y(0.582), Y(0.20), [g(48), g(55), g(62)], 80, 14, opacity=0.8, color_jitter=0.0, grain=0.3)
    band_strokes(c, -40, Y(0.61), [g(68), g(75)], 90, 8, opacity=0.8, color_jitter=0.0, grain=0.3)
    band_strokes(c, Y(0.30), Y(0.18), [g(85), g(100), g(75)], 50, 5, tip="chalk", opacity=0.6,
                 color_jitter=0.0, grain=0.6)  # worn foot
    for (x, y, r) in CHIPS:
        c.stroke(curve((x - r * 0.8, y), (x, y), (x + r * 0.9, y)), g(150), r * 1.9, opacity=0.95,
                 tip="chalk", seed=next(seed), color_jitter=0.0, grain=0.4)
    return c


if __name__ == "__main__":
    t = time.time()
    a = paint_albedo()
    a.save(OUT + r"\jug.png"); a.save_log(OUT + r"\jug.json")
    print(f"jug albedo: {len(a.log)} strokes in {time.time() - t:.1f}s")
    t = time.time()
    r = paint_rough()
    r.save(OUT + r"\jug_rough_rgb.png"); r.save_log(OUT + r"\jug_rough.json")
    from PIL import Image
    Image.open(OUT + r"\jug_rough_rgb.png").convert("L").save(OUT + r"\jug_rough.png")
    import os
    os.remove(OUT + r"\jug_rough_rgb.png")
    print(f"jug roughness: {len(r.log)} strokes in {time.time() - t:.1f}s")
