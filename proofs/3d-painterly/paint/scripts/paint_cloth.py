"""Linen cloth albedo: 38x30 cm, image x = length. Off-white linen with a faded indigo border.

Run: uv run --with numpy --with pillow python -I paint_cloth.py
"""
import sys, time
sys.path.insert(0, r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint")
import numpy as np
from brush import Canvas, curve

OUT = r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint\textures"
N = 2048
rng = np.random.default_rng(11)
seed = iter(range(1, 10 ** 6))

LINEN, WARM, COOL = (0.86, 0.83, 0.75), (0.90, 0.82, 0.68), (0.78, 0.80, 0.82)
INDIGO, FADED = (0.24, 0.30, 0.50), (0.45, 0.52, 0.66)


def mix(a, b, t):
    return tuple(float(x + (y - x) * t) for x, y in zip(a, b))


def line(x0, y0, x1, y1, wob, pr=(.5, 1, .4)):
    k = 4
    return curve(*[(x0 + (x1 - x0) * i / k + rng.normal(0, wob), y0 + (y1 - y0) * i / k + rng.normal(0, wob))
                   for i in range(k + 1)], n=16, pressure=pr)


def paint():
    c = Canvas(N, N, fill=LINEN, grain_seed=21, grain_size=2.0)
    # block-in: broad strokes along the length, warm and cool off-whites
    for y in np.arange(-40, N + 80, 70):
        x = rng.uniform(-400, 0)
        while x < N:
            L = rng.uniform(400, 800)
            col = mix(LINEN, WARM if rng.random() < .55 else COOL, rng.uniform(.2, .7))
            c.stroke(line(x, y, x + L, y, 3), col, rng.uniform(90, 130), tip="flat", hardness=.7, opacity=.8, grain=.3,
                     color_jitter=.04, seed=next(seed))
            x += L * rng.uniform(.6, .9)
    # weave: faint cross strokes along the width, broken on the tooth
    for x in np.arange(0, N, 45):
        y = rng.uniform(-300, 0)
        while y < N:
            L = rng.uniform(300, 700)
            c.stroke(line(x, y, x, y + L, 4), mix(LINEN, COOL, .8), rng.uniform(20, 40), tip="bristle",
                     opacity=.25, grain=.5, color_jitter=.03, seed=next(seed))
            y += L
    # border: two faded indigo stripes inside each long edge and one thin stripe at each short end
    for yc, w in ((150, 70), (270, 26), (N - 150, 70), (N - 270, 26)):
        for _ in range(3):
            x = rng.uniform(-300, -50)
            while x < N + 50:
                L = rng.uniform(500, 900)
                col = mix(INDIGO, FADED, rng.uniform(.1, .6))
                c.stroke(line(x, yc + rng.normal(0, w * .04), x + L, yc + rng.normal(0, w * .04), 1), col,
                         w * rng.uniform(.9, 1.15), tip="bristle", opacity=.85, grain=.35, color_jitter=.06,
                         seed=next(seed))
                x += L * rng.uniform(.6, .9)
    for xc in (110, N - 110):
        for _ in range(2):
            c.stroke(line(xc, -40, xc, N + 40, 1), mix(INDIGO, FADED, rng.uniform(.3, .7)), 34, tip="bristle",
                     opacity=.7, grain=.45, color_jitter=.06, seed=next(seed))
    # fading: washed-out patches lift the indigo and warm the white unevenly
    for _ in range(14):
        x, y = rng.uniform(0, N), rng.uniform(0, N)
        c.stroke(line(x, y, x + rng.uniform(200, 450), y + rng.normal(0, 40), 20), mix(LINEN, WARM, rng.uniform(0, .5)),
                 rng.uniform(80, 160), tip="flat", opacity=.3, grain=.55, color_jitter=.05, seed=next(seed))
    # folds: in the frame the cloth is ~700x200 px (1/3 across x, ~1/10 across y), so each fold is a
    # broad cool shadow stroke with a warm lit ridge beside it, wide in y so it survives the squash
    for _ in range(6):
        x, y = rng.uniform(-200, N - 600), rng.uniform(350, N - 450)
        dx, dy = rng.uniform(700, 1300), rng.normal(0, 120)
        sh, ri = line(x, y, x + dx, y + dy, 30, pr=(.2, 1, .15)), line(x + 20, y + 110, x + dx * .9, y + dy + 110, 30,
                                                                          pr=(.2, 1, .15))
        c.stroke(sh, mix(COOL, (0.50, 0.53, 0.64), rng.uniform(.5, .8)), rng.uniform(150, 220), tip="flat",
                 hardness=.6, opacity=.7, grain=.2, color_jitter=.05, size_pressure=.6, seed=next(seed))
        c.stroke(ri, mix(WARM, (1.0, 0.95, 0.84), .7), rng.uniform(80, 120), tip="flat", hardness=.7,
                 opacity=.85, grain=.3, color_jitter=.04, size_pressure=.6, seed=next(seed))
    # cross-strokes: a few loose broad strokes across the width, a clear step warmer or cooler
    for _ in range(9):
        x = rng.uniform(0, N)
        col = mix(LINEN, WARM if rng.random() < .5 else (0.68, 0.71, 0.78), rng.uniform(.6, .9))
        c.stroke(line(x, rng.uniform(-100, 600), x + rng.normal(0, 120), rng.uniform(1400, N + 100), 25,
                      pr=(.3, 1, .2)), col, rng.uniform(110, 170), tip="flat", hardness=.7, opacity=.5, grain=.35,
                 color_jitter=.05, size_pressure=.5, seed=next(seed))
    # hem: a slightly darker folded edge all round
    for pts in (line(-40, 18, N + 40, 18, 2), line(-40, N - 18, N + 40, N - 18, 2),
                line(18, -40, 18, N + 40, 2), line(N - 18, -40, N - 18, N + 40, 2)):
        c.stroke(pts, mix(LINEN, (0.6, 0.58, 0.55), .5), 40, tip="bristle", opacity=.6, color_jitter=.04,
                 seed=next(seed))
    return c


if __name__ == "__main__":
    t = time.time()
    c = paint()
    c.save(f"{OUT}\\cloth.png"); c.save_log(f"{OUT}\\cloth.json")
    print("cloth", len(c.log), "strokes", round(time.time() - t, 1), "s")
