"""Table top: albedo, roughness and height for a 75x75 cm tile of old oiled planks.

The tile repeats, so every stroke is painted with wrap-around copies (see `wrap`).
Six planks of 2048/6 px (~12.5 cm) run along image x. In the 1080p frame a plank is only
~60-90 px tall (about 1/5 of the texture), so strokes are broad (1/3-1/2 plank) and the value
steps between neighbouring strokes are large, or the brushwork melts into smooth wood.

All three maps come from ONE list of marks (`marks()`): each mark carries its colour plus the
height and roughness it stands for, so ridges and shiny worn spots land on the painted strokes.
Run: uv run --with numpy --with pillow python -I paint_table.py [table table_height table_rough]
"""
import sys, time
sys.path.insert(0, r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint")
import numpy as np
from brush import Canvas, curve

OUT = r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint\textures"
N = 2048
PLANK = N / 6
GRAIN = dict(grain_seed=3, grain_size=3.0)  # same tooth on every map, so chalk breaks line up


def mix(a, b, t):
    return tuple(float(x + (y - x) * t) for x, y in zip(a, b))


DARK, MID, LIGHT = (0.24, 0.14, 0.09), (0.55, 0.36, 0.21), (0.84, 0.64, 0.42)
COOL, PAINT = (0.50, 0.46, 0.47), (0.42, 0.55, 0.50)  # worn grey-violet, faded old green paint


def marks():
    """Every stroke of the table as data: (points, colour, height, roughness, stroke kwargs)."""
    rng = np.random.default_rng(7)
    seed = iter(range(1, 10 ** 6))
    out = []

    def add(pts, col, h, r, size, **kw):
        out.append((pts, col, h, r, dict(size=size, seed=next(seed), **kw)))

    def run(x0, y, length, wob, n=16, pr=(0.4, 1.0, 0.3)):
        ctrl = [(x0 + length * i / 4, y + rng.normal(0, wob)) for i in range(5)]
        return curve(*ctrl, n=n, pressure=pr)

    tones = [0.18, 0.66, 0.38, 0.8, 0.26, 0.55]  # each plank its own lightness
    knots = {1: 1, 4: 1}  # plank -> number of knots
    for k in range(6):
        top = k * PLANK
        base = mix(mix(DARK, LIGHT, tones[k]), ((0.5, 0.40, 0.38), (0.62, 0.30, 0.17), MID)[k % 3], .3)
        add(run(-200, top + PLANK / 2, N + 400, 0, n=8, pr=(1, 1, 1)), base, .45, .6, PLANK + 20,
            tip="flat", hardness=.9, angle=90, color_jitter=.03)
        # block-in: 4 overlapping lanes of broad loaded strokes, each a clear value step from its
        # neighbours; a lane covers one full tile width from wherever it starts (wrap does the rest)
        for lane in range(4):
            y = top + PLANK * (lane + .5) / 4
            x0 = x = rng.uniform(-N / 2, N / 2)
            last = 0
            while x < x0 + N:
                L = rng.uniform(350, 750)
                step = rng.choice([-.5, -.35, .3, .45, .55])
                if np.sign(step) == last:  # alternate light/dark so the joins read
                    step = -step
                last = np.sign(step)
                col = mix(base, LIGHT if step > 0 else DARK, abs(step))
                if rng.random() < .3:  # temperature shift: some strokes warm red, some cool grey
                    col = mix(col, (0.58, 0.30, 0.16) if rng.random() < .5 else COOL, .3)
                add(run(x, y + rng.normal(0, 12), L, 6, pr=(.7, 1, .6)), col, .5 + .25 * step,
                    .55 - .15 * step, rng.uniform(100, 150), tip="bristle", hardness=.8, opacity=1,
                    color_jitter=.06, size_pressure=.35)
                x += L * rng.uniform(.75, 1.05)
        # grain: a few long dark strokes, thick enough to survive the downscale
        for _ in range(6):
            add(run(rng.uniform(0, N), top + rng.uniform(30, PLANK - 30), rng.uniform(600, 1300), 14,
                    pr=(.2, 1, .1)), mix(base, DARK, rng.uniform(.6, .9)), .28, .75, rng.uniform(10, 18),
                tip="bristle", opacity=.9, color_jitter=.05)
        # grime along both plank edges
        for y in (top + 18, top + PLANK - 18):
            add(run(rng.uniform(0, N), y, N * .8, 3, pr=(.3, 1, .3)), mix(base, DARK, .7), .35, .8, 40,
                tip="bristle", opacity=.75, color_jitter=.04)
        # dry-brush lights: the brightest marks, broken on the tooth (worn ridges, oily = shiny)
        for _ in range(4):
            add(run(rng.uniform(0, N), top + rng.uniform(40, PLANK - 40), rng.uniform(250, 700), 8,
                    pr=(.25, 1, .1)), mix(base, LIGHT, rng.uniform(.7, 1)), .8, .3, rng.uniform(35, 95),
                tip="bristle", opacity=1, color_jitter=.05, grain=.35, size_pressure=.6)
        # knots: a ragged dark eye and broken grain arcs bending round it (no closed rings)
        for _ in range(knots.get(k, 0)):
            kx, ky = rng.uniform(200, N - 200), top + rng.uniform(120, PLANK - 120)
            for _ in range(3):
                a = rng.uniform(0, np.pi)
                d = np.array([np.cos(a), .45 * np.sin(a)]) * rng.uniform(14, 26)
                add(curve((kx - d[0], ky - d[1]), (kx + rng.normal(0, 6), ky + rng.normal(0, 4)),
                          (kx + d[0], ky + d[1]), n=8, pressure=(.6, 1, .5)),
                    mix(DARK, (0.12, 0.07, 0.05), .6), .2, .7, rng.uniform(26, 40), tip="bristle", opacity=.95)
            for j in range(4):
                rx, ry = 50 + 38 * j + rng.uniform(-10, 10), 22 + 13 * j + rng.uniform(-4, 4)
                t0 = rng.uniform(0, 2 * np.pi)
                ts = np.linspace(t0, t0 + rng.uniform(2.2, 3.6), 9)
                wob = 1 + .15 * np.sin(ts * rng.uniform(2, 4) + rng.uniform(0, 6))
                pts = curve(*[(kx + rx * w * np.cos(t), ky + ry * w * np.sin(t)) for t, w in zip(ts, wob)],
                            n=24, pressure=(.2, 1, .2))
                add(pts, mix(DARK, base, .1 + .15 * j), .3, .7, rng.uniform(14, 22) - 2 * j, tip="bristle",
                    opacity=1)
    # traces of old green paint clinging near plank edges (raised, dry)
    for _ in range(10):
        k = rng.integers(6)
        y = k * PLANK + (rng.uniform(14, 50) if rng.random() < .5 else PLANK - rng.uniform(14, 50))
        add(run(rng.uniform(0, N), y, rng.uniform(180, 420), 4, pr=(.2, 1, .1)),
            mix(PAINT, COOL, rng.uniform(.3, .7)), .72, .85, rng.uniform(30, 60), tip="chalk", opacity=.9,
            grain=.5, color_jitter=.08)
    # worn, rubbed lighter areas (hands, plates): smooth and shiny
    for _ in range(7):
        add(run(rng.uniform(0, N), rng.uniform(0, N), rng.uniform(300, 550), 20),
            mix(LIGHT, COOL, rng.uniform(0, .5)), .55, .22, rng.uniform(110, 170), tip="flat", opacity=.35,
            grain=.45, color_jitter=.1)
    # plank gaps: dark seam with a lit bevel just below; straight, full width, pressure 1 (no stepping)
    for k in range(6):
        y = k * PLANK
        add(run(-300, y, N + 600, 0, n=24, pr=(1, 1, 1)), (0.10, 0.06, 0.05), .02, .95, 12, tip="round",
            hardness=.75, opacity=.95, color_jitter=0, size_pressure=0)
        add(run(-300, y + 11, N + 600, 1.5, n=24, pr=(1, 1, 1)), mix(LIGHT, COOL, .25), .62, .4, 9,
            tip="bristle", opacity=.6)
    return out


def wrap(c, pts, *a, **kw):
    """Stroke plus its copies shifted by one tile, so paint crossing an edge continues on the other side."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    r = kw.get("size", 50)
    for dx in (-N, 0, N):
        for dy in (-N, 0, N):
            if max(xs) + dx + r < 0 or min(xs) + dx - r > N or max(ys) + dy + r < 0 or min(ys) + dy - r > N:
                continue
            c.stroke([(x + dx, y + dy, p) for x, y, p in pts], *a, **kw)


def paint(which):
    """which: 0 = colour, 1 = height, 2 = roughness. Same strokes, different paint."""
    fill = (MID, (.45,) * 3, (.6,) * 3)[which]
    c = Canvas(N, N, fill=fill, **GRAIN)
    for pts, col, h, r, kw in marks():
        if which:
            v = (h, r)[which - 1]
            col, kw = (v, v, v), {**kw, "color_jitter": .03 if which == 1 else 0}
        wrap(c, pts, col, **kw)
    return c


if __name__ == "__main__":
    for i, name in enumerate(("table", "table_height", "table_rough")):
        if len(sys.argv) > 1 and name not in sys.argv[1:]:
            continue
        t = time.time()
        c = paint(i)
        c.save(f"{OUT}\\{name}.png"); c.save_log(f"{OUT}\\{name}.json")
        print(name, len(c.log), "strokes", round(time.time() - t, 1), "s")
