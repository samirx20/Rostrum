"""Background card (2560x1440): the room's back wall, sun patch from a window off-frame left.

A finished painting with its light painted in (emissive in the scene). Interest in the upper ~55 %;
the lower half sits behind the table. Values kept a little under the lit props.
Run: uv run --with numpy --with pillow python -I paint_background.py
"""
import sys, time
sys.path.insert(0, r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint")
import numpy as np
from brush import Canvas, curve

OUT = r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint\textures"
W, H = 2560, 1440
rng = np.random.default_rng(5)
seed = iter(range(1, 10 ** 6))

WALL, WALL_DK = (0.36, 0.38, 0.45), (0.25, 0.27, 0.34)          # plaster in cool room shadow
SUN, SUN_HOT = (0.70, 0.53, 0.40), (0.78, 0.61, 0.45)           # warm low sun on the plaster
EDGE = (0.62, 0.42, 0.36)                                      # warm-to-cool turn at the patch edge
DOOR, DOOR_IN = (0.17, 0.17, 0.22), (0.34, 0.27, 0.24)
WOOD = (0.30, 0.21, 0.17)


def mix(a, b, t):
    return tuple(float(x + (y - x) * t) for x, y in zip(a, b))


def line(*pts, wob=6, pr=(.5, 1, .4)):
    return curve(*[(x + rng.normal(0, wob), y + rng.normal(0, wob)) for x, y in pts], n=20, pressure=pr)


def paint():
    c = Canvas(W, H, fill=WALL, grain_seed=9, grain_size=4.0)
    full = c.mask_from_polygon([(0, 0), (W, 0), (W, H), (0, H)])
    # 1. wall block-in: big diagonal strokes, cooler and darker toward the right and the floor
    c.fill_region(full, WALL, 170, angle=-65, gap=.55, length=1.8, bend=.04, seed=next(seed), pressure=(.85, 1, .8), size_pressure=.15, tip="flat",
                  hardness=.7, opacity=.7, color_jitter=.06)
    for _ in range(40):
        x, y = rng.uniform(1200, W), rng.uniform(0, H)
        c.stroke(line((x, y), (x + 100, y + 240), wob=3), mix(WALL, WALL_DK, rng.uniform(.3, .9)), rng.uniform(120, 200),
                 tip="flat", hardness=.7, opacity=.5, color_jitter=.05, grain=.3, seed=next(seed))
    for _ in range(18):  # warm light bounced off the table and floor rises up the lower-left wall
        x, y = rng.uniform(0, 1500), rng.uniform(500, 1000)
        c.stroke(line((x, y), (x + 90, y - 200), wob=3), mix(WALL, (0.55, 0.45, 0.42), rng.uniform(.3, .7)),
                 rng.uniform(110, 180), tip="flat", hardness=.7, opacity=.4, grain=.3, color_jitter=.05,
                 seed=next(seed))
    # wainscot: a darker painted dado below a rail, mostly hidden by the table
    dado = c.mask_from_polygon([(0, 760), (W, 740), (W, H), (0, H)])
    c.fill_region(dado, (0.30, 0.33, 0.36), 130, angle=90, gap=.6, length=2, bend=.02, seed=next(seed), pressure=(.85, 1, .8), size_pressure=.15,
                  tip="flat", hardness=.7, opacity=.85, color_jitter=.05)
    c.stroke(line((-50, 752), (1300, 748), (W + 50, 738), wob=2, pr=(1, 1, 1)), (0.44, 0.42, 0.42), 22,
             tip="flat", angle=90, opacity=.9, seed=next(seed))
    # 2. sun patch: a skewed window shape (two panes) thrown onto the wall from the left
    panes = [[(250, 130), (720, 80), (760, 640), (300, 700)], [(800, 70), (1240, 25), (1280, 585), (840, 630)]]
    for poly in panes:  # rosy half-light first: a wide soft rim where the light turns to shadow
        m = c.mask_from_polygon(poly, feather=70)
        c.fill_region(m, EDGE, 140, angle=-75, gap=.5, length=1.6, bend=.03, seed=next(seed), pressure=(.85, 1, .8),
                      size_pressure=.15, tip="flat", hardness=.5, opacity=.5, color_jitter=.04)
    for poly in panes:
        m = c.mask_from_polygon(poly, feather=24)
        c.fill_region(m, SUN, 130, angle=-75, gap=.45, length=1.6, bend=.03, seed=next(seed), pressure=(.85, 1, .8),
                      size_pressure=.15, tip="flat", hardness=.7, opacity=1, color_jitter=.03)
        for _ in range(5):  # a few hotter strokes toward the top of each pane
            x, y = rng.uniform(poly[0][0] + 80, poly[1][0] - 80), rng.uniform(poly[1][1] + 80, poly[1][1] + 300)
            c.stroke(line((x, y), (x + 40, y + 180), wob=3), SUN_HOT, rng.uniform(90, 130), tip="flat",
                     hardness=.7, opacity=.4, color_jitter=.03, grain=.4, mask=m, seed=next(seed))
    c.stroke(line((150, 350), (700, 380), (1350, 300), wob=20), SUN, 520, tip="round", hardness=.05,
             opacity=.18, seed=next(seed))
    # 3. doorway on the right: dark opening, a glimpse of a warmer room, painted frame
    door = c.mask_from_polygon([(1890, 60), (2330, 60), (2330, H), (1890, H)])
    c.fill_region(door, DOOR, 130, angle=90, gap=.5, length=2, bend=.02, seed=next(seed), pressure=(.85, 1, .8), size_pressure=.15, tip="flat",
                  hardness=.8, opacity=1, color_jitter=.05)
    beyond = c.mask_from_polygon([(1980, 180), (2240, 180), (2240, 900), (1980, 900)], feather=40)
    c.fill_region(beyond, DOOR_IN, 100, angle=95, gap=.6, length=2, bend=.02, seed=next(seed), pressure=(.85, 1, .8), size_pressure=.15, tip="flat",
                  hardness=.7, opacity=.6, color_jitter=.06)
    for x in (1880, 2340):
        c.stroke(line((x, 50), (x, H + 40), wob=3, pr=(1, 1, 1)), (0.40, 0.40, 0.44), 46, tip="bristle",
                 opacity=.9, color_jitter=.06, seed=next(seed))
    c.stroke(line((1850, 52), (2370, 48), wob=2, pr=(1, 1, 1)), (0.42, 0.42, 0.46), 50, tip="bristle", opacity=.9,
             seed=next(seed))
    # 4. a shelf on the wall with a few jars, half in light
    c.stroke(line((1330, 470), (1800, 462), wob=1, pr=(1, 1, 1)), WOOD, 26, tip="flat", angle=90, opacity=.95,
             seed=next(seed))
    c.stroke(line((1330, 488), (1800, 480), wob=1, pr=(1, 1, 1)), (0.18, 0.18, 0.24), 22, tip="round",
             hardness=.2, opacity=.5, seed=next(seed))  # its cast shadow on the plaster
    for x, w, h, col in ((1390, 70, 150, (0.58, 0.42, 0.30)), (1480, 50, 95, (0.30, 0.38, 0.40)),
                         (1580, 90, 120, (0.52, 0.47, 0.42)), (1700, 40, 170, (0.24, 0.30, 0.28))):
        c.stroke(line((x, 455), (x + 4, 455 - h), wob=2, pr=(1, 1, .8)), col, w, tip="bristle", opacity=.95,
                 color_jitter=.08, seed=next(seed))
        c.stroke(line((x - w * .25, 452), (x - w * .2, 455 - h * .8), wob=1), mix(col, SUN_HOT, .6), w * .3,
                 tip="bristle", opacity=.7, seed=next(seed))  # light catches the left side
    # 5. a chair back by the door, dark against the wall, warm rim on its top rail
    for x in (1600, 1790):
        c.stroke(line((x, 1300), (x + 5, 900), (x + 12, 640), wob=3), WOOD, 34, tip="bristle", opacity=.9,
                 seed=next(seed))
    c.stroke(line((1585, 650), (1700, 630), (1815, 640), wob=3, pr=(1, 1, 1)), WOOD, 46, tip="bristle",
             opacity=.95, seed=next(seed))
    c.stroke(line((1590, 632), (1700, 612), (1810, 622), wob=2), mix(WOOD, SUN, .5), 12, tip="bristle",
             opacity=.6, seed=next(seed))
    c.stroke(line((1600, 760), (1700, 750), (1790, 760), wob=3, pr=(1, 1, 1)), WOOD, 26, tip="bristle",
             opacity=.9, seed=next(seed))
    # 6. unify: soften everything a touch with a wet pass, as if slightly out of focus
    for x in np.arange(0, W, 220):
        c.stroke(line((x, -50), (x + 60, H / 2), (x + 120, H + 50), wob=10), WALL, 160, tip="flat", wet=.5,
                 opacity=.35, seed=next(seed))
    return c


if __name__ == "__main__":
    t = time.time()
    c = paint()
    c.save(f"{OUT}\\background.png"); c.save_log(f"{OUT}\\background.json")
    print("background", len(c.log), "strokes", round(time.time() - t, 1), "s")
