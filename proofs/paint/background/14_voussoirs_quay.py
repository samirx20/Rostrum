# Round 2, surface pass 7: the arch ring as worn, separate stones (radial strokes, dark joints, warm lower faces),
# and the quay and boat painted along their planes instead of flat fills.
import math, random
from brush import curve
from _geo import *

R = random.Random(147)
A = "agent:painter2"
CX, WL = 980, 712


def jit(c, k=0.12):
    return tuple(min(1, max(0, v * R.uniform(1 - k, 1 + k))) for v in c)


def ring(a, r):  # point on an ellipse r times the arch
    return CX + 320 * r * math.cos(a), WL - 124 * r * math.sin(a)


with doc.batch("arch ring stones", author=A):
    ids = []
    N = 31
    for i in range(N):
        a0, a1 = math.pi * i / N, math.pi * (i + 1) / N
        am = (a0 + a1) / 2
        r_out = R.uniform(1.09, 1.15)
        p0, p1 = ring(am, 1.01), ring(am, r_out)
        light = 0.5 + 0.5 * math.sin(am)  # crown stones sit nearest the light
        c = jit(mix(BRIDGE, (0.46, 0.35, 0.36), 0.15 + 0.35 * light), 0.06)
        w = 320 * (a1 - a0) * (0.55 + 0.45 * abs(math.sin(am))) * 0.75 + 3
        ids.append(doc.stroke("stone", [(p0[0], p0[1], 1), (p1[0], p1[1], 0.8)], c, w, brush=R.choice(("block", "chalk")),
                              mask="bridge", size_pressure=0.2, opacity=R.uniform(0.35, 0.6), color_jitter=0.04, grain=0.6,
                              seed=R.randrange(99999)))
        j0, j1 = ring(a1, 1.0), ring(a1, r_out - 0.02)  # joint
        doc.stroke("stone", [(j0[0], j0[1], 1), (j1[0], j1[1], 0.5)], (0.08, 0.07, 0.10), R.uniform(1.5, 3), brush="line",
                   mask="bridge", opacity=0.7)
        q0, q1 = ring(am, 1.0), ring(am, 1.05)  # warm lower face catching the glow from under the arch
        doc.stroke("stone", [(q0[0], q0[1], 1), (q1[0], q1[1], 0.6)], (0.75, 0.50, 0.38), w * 0.8, brush="flat",
                   mask="bridge", opacity=0.35 + 0.4 * light, seed=R.randrange(99999))
    print("ring stone ids", ids[:3])

with doc.batch("quay and boat painted", author=A):
    doc.add_layer("quay_paint", below="near")
    for m, base, n in (("quay_top", (0.30, 0.27, 0.33), 110), ("quay_face", (0.13, 0.12, 0.17), 90), ("boat", (0.10, 0.09, 0.12), 70)):
        ys_x = doc.mask_array(m)
        import numpy as np
        ys, xs = np.nonzero(ys_x > 0.5)
        for k in range(n):
            j = R.randrange(len(xs))
            x, y = int(xs[j]), int(ys[j])
            ux, uy = VP[0] - x, VP[1] - y
            d = math.hypot(ux, uy) or 1
            L = R.uniform(40, 160) * (0.4 + 0.8 * abs(x - 1000) / 1000)
            lamp = max(0, 1 - math.hypot(x - 380, (y - 800) * 2) / 360) if m != "boat" else max(0, 1 - abs(x - 1765) / 200)
            c = jit(mix(base, (0.72, 0.50, 0.32), lamp * R.uniform(0.3, 0.8)))
            doc.stroke("quay_paint", curve((x, y), (x + ux / d * L / 2, y + uy / d * L / 2 + R.uniform(-1, 1)), (x + ux / d * L, y + uy / d * L),
                                           n=10, pressure=(0.5, 1, 0.3)), c, R.uniform(6, 18), brush=R.choice(("flat", "bristle", "chalk")),
                       mask=m, opacity=R.uniform(0.45, 0.85), color_jitter=0.1, grain=0.5, seed=R.randrange(99999))
    for i in range(14):  # paving joints across the quay top, converging like the walls
        x = 30 + i * 42
        doc.stroke("quay_paint", [(x, 790 + 2, 1), (x + 8, 834, 1)], (0.12, 0.11, 0.15), 2, brush="line", mask="quay_top", opacity=0.6)
