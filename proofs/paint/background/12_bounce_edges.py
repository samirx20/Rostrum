# Round 2, surface pass 5: colour inside the shadows and lost edges. Warm light bounced up from the lit water onto
# the lower walls, cool sky light on the upper walls (both as screen strokes, so they stack), then wet drags that
# lose the arch's inner edge, the tops of the far canal walls and the far rooflines into the glow.
import math, random
import numpy as np
from brush import curve
from _geo import *

R = random.Random(125)
A = "agent:painter2"
CX, WL = 980, 712
SIDES = {"br0": 880, "br1": 880, "br2": 880, "br3": 880, "br4": 880, "bl0": 790, "bl1": 790, "bl2": 790}


def inside(m, n):
    ys, xs = np.nonzero(doc.mask_array(m) > 0.5)
    return [(int(xs[j]), int(ys[j])) for j in (R.randrange(len(xs)) for _ in range(n))]


with doc.batch("bounce and sky light on walls", author=A):
    doc.add_layer("wall_light", below="wall_air", mode="screen")
    n = 0
    for m, base in SIDES.items():
        for x, y in inside(m, 45):
            ux, uy = VP[0] - x, VP[1] - y
            d = math.hypot(ux, uy) or 1
            scale = 0.4 + 0.9 * abs(x - 1000) / 920
            L = R.uniform(80, 240) * scale
            low = y > base - 260  # near the water: warm bounce, stronger toward the bright reflection
            k = max(0.2, 1 - abs(x - CX) / 900)
            c = (0.16 * k, 0.09 * k, 0.05 * k) if low else (0.04, 0.05, 0.09)
            doc.stroke("wall_light", curve((x - ux / d * L / 2, y - uy / d * L / 2), (x, y), (x + ux / d * L / 2, y + uy / d * L / 2),
                                           n=12, pressure=(0.3, 1, 0.3)), c, R.uniform(20, 50) * scale, brush="bristle",
                       mask=m, opacity=R.uniform(0.5, 0.9), color_jitter=0.2, grain=0.5, seed=R.randrange(99999))
            n += 1
    print("wall light strokes", n)

with doc.batch("lost edges", author=A):
    doc.add_layer("edges", below="near")
    ids = []
    for i in range(26):  # along the arch's inner edge, strongest at the crown where the light is
        a = math.pi * R.uniform(0.25, 0.75)
        x, y = CX + 320 * math.cos(a), WL - 124 * math.sin(a)
        tx, ty = -math.sin(a) * 320, math.cos(a) * 124  # tangent
        t = math.hypot(tx, ty)
        L = R.uniform(30, 70)
        ids.append(doc.stroke("edges", [(x - tx / t * L / 2, y - ty / t * L / 2 + 3, 0.6), (x, y, 1), (x + tx / t * L / 2, y + ty / t * L / 2 - 3, 0.6)],
                              (0.6, 0.45, 0.45), R.uniform(8, 16), brush="round", hardness=0.2, wet=0.8, sample_all=True,
                              opacity=0.8, seed=R.randrange(99999)))
    for x0, x1 in ((660, 900), (1070, 1320)):  # tops of the far canal walls under the arch
        for i in range(10):
            x = R.uniform(x0, x1)
            y = 600 + (x - x0) / (x1 - x0) * 20 if x0 < 900 else 616 - (x - x0) / (x1 - x0) * 20
            ids.append(doc.stroke("edges", [(x - 25, y + R.uniform(-4, 4), 0.6), (x + 25, y + R.uniform(-4, 4), 1)],
                                  (0.6, 0.45, 0.45), R.uniform(8, 14), brush="round", hardness=0.2, wet=0.75,
                                  sample_all=True, opacity=0.8, seed=R.randrange(99999)))
    for x0, x1, y0, side in ((1340, 1400, 120, "r"), (1400, 1500, -150, "r"), (460, 620, 110, "l")):  # far rooflines
        for i in range(8):
            x = R.uniform(x0, x1)
            y = right_y(y0, x) if side == "r" else left_y(y0, x)
            ids.append(doc.stroke("edges", [(x - 12, y - 6, 0.7), (x + 12, y + 6, 1)], (0.5, 0.4, 0.5), R.uniform(8, 14),
                                  brush="round", hardness=0.3, wet=0.7, sample_all=True, opacity=0.7, seed=R.randrange(99999)))
    print("edge drag ids", ids[:2], len(ids))
