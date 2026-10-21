# Round 2, surface pass 3 (all dry strokes, so it stays fast): stone on the bridge in a narrow value range,
# brushwork in the canal seen through the arch, a painted sky, and detail on the near walls where the eye goes
# (drainpipes, shutters, lit corner edges, chimneys).
import math, random
import numpy as np
from brush import curve
from _geo import *

R = random.Random(103)
A = "agent:painter2"
CX, WL = 980, 712


def jit(c, k=0.12):
    return tuple(min(1, max(0, v * R.uniform(1 - k, 1 + k))) for v in c)


def inside(m, n):
    ys, xs = np.nonzero(doc.mask_array(m) > 0.5)
    return [(int(xs[j]), int(ys[j])) for j in (R.randrange(len(xs)) for _ in range(n))]


with doc.batch("bridge stone, take two", author=A):
    doc.add_layer("stone", below="wall_r")
    for x, y in inside("bridge", 300):
        rim = max(0, 1 - abs(math.hypot((x - CX) / 320, (y - WL) / 124) - 1) * 4)
        c = mix(BRIDGE, (0.40, 0.30, 0.32), R.uniform(0.1, 0.5))
        c = mix(c, (0.62, 0.42, 0.36), rim * R.uniform(0.2, 0.6))
        L = R.uniform(25, 70)
        doc.stroke("stone", curve((x, y), (x + L / 2, y + R.uniform(-1.5, 1.5)), (x + L, y), n=10, pressure=(0.6, 1, 0.4)),
                   jit(c), R.uniform(9, 20), brush=R.choice(("flat", "chalk", "bristle")), mask="bridge",
                   opacity=R.uniform(0.3, 0.6), color_jitter=0.08, grain=0.55, seed=R.randrange(99999))

with doc.batch("through the arch, painted", author=A):
    doc.add_layer("arch_paint", below="stone")
    for m, base in (("far_canal_l", (0.52, 0.40, 0.48)), ("far_canal_r", (0.54, 0.42, 0.48))):
        for x, y in inside(m, 70):
            ux, uy = VP[0] - x, VP[1] - y
            d = math.hypot(ux, uy) or 1
            L = R.uniform(20, 60)
            c = mix(base, SKY_GLOW, R.uniform(0, 0.35) * (1 - d / 360))
            doc.stroke("arch_paint", [(x, y, 0.6), (x + ux / d * L, y + uy / d * L, 1)], jit(c), R.uniform(6, 16),
                       brush=R.choice(("flat", "bristle")), mask=m, opacity=R.uniform(0.4, 0.8), grain=0.4,
                       seed=R.randrange(99999))
        for x, y in inside(m, 16):  # vertical light seams: doors and corners down there
            doc.stroke("arch_paint", [(x, y - 10, 1), (x, y + 12, 0.4)], (0.30, 0.22, 0.30), R.uniform(2, 4),
                       brush="line", mask=m, opacity=0.7)
    for x, y in inside("far_water", 90):  # the far water: long warm strokes, value rising toward the hot centre
        k = max(0, 1 - abs(x - CX) / 340)
        c = mix((0.70, 0.52, 0.48), SKY_HOT, k * R.uniform(0.3, 0.9))
        L = R.uniform(30, 120)
        doc.stroke("arch_paint", [(x - L / 2, y, 0.3), (x, y + R.uniform(-1, 1), 1), (x + L / 2, y, 0.3)], jit(c, 0.06),
                   R.uniform(3, 9), brush=R.choice(("flat", "bristle")), mask="far_water", opacity=R.uniform(0.4, 0.8),
                   seed=R.randrange(99999))

with doc.batch("sky brushwork", author=A):
    doc.add_layer("sky_paint", below="clouds")
    sky = doc.layer_pixels("sky")
    for i in range(240):
        x, y = R.uniform(0, 1920), R.random() ** 0.8 * 560
        c = sky[int(y), int(x), :3]
        c = mix(c, SKY_GLOW, R.uniform(0, 0.25) * max(0, y - 250) / 310) if R.random() < 0.6 else c
        L = R.uniform(120, 380)
        tilt = R.uniform(-0.06, 0.06)
        doc.stroke("sky_paint", curve((x - L / 2, y - L / 2 * tilt), (x, y + R.uniform(-8, 8)), (x + L / 2, y + L / 2 * tilt),
                                      n=16, pressure=(0.3, 1, 0.3)), jit(c, 0.08), R.uniform(30, 80),
                   brush=R.choice(("bristle", "flat")), opacity=R.uniform(0.35, 0.7), color_jitter=0.06, hue_jitter=4,
                   grain=0.35, seed=R.randrange(99999))

