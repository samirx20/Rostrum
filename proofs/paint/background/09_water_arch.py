# Round 2, surface pass 2: the focus. Break the hard ellipse of light under the arch into painted ripples
# (wet drags across its rim, dark ripples cutting in, warm ripples spilling out), then stone brushwork on the
# bridge and a soft glow that loses the arch's top edge into the light.
import math, random
import numpy as np
from brush import curve
from _geo import *

R = random.Random(92)
A = "agent:painter2"
CX, WL = 980, 712  # arch centre x, water line


def ripple(layer, x, y, L, size, c, **kw):
    p = [(x - L / 2 + L * i / 7, y + math.sin(i * 1.3 + x) * 1.2, (0.2, 0.7, 1, 1, 1, 0.8, 0.5, 0.15)[i]) for i in range(8)]
    return doc.stroke(layer, p, c, size, seed=R.randrange(99999), **kw)


with doc.batch("ellipse rim dragged", author=A):
    doc.add_layer("water_paint", below="near")
    n = 0
    for i in range(260):  # wet horizontal drags along the rim of the bright reflection
        a = R.uniform(0, math.pi)
        rx, ry = 330 * R.uniform(0.85, 1.12), 170 * R.uniform(0.8, 1.15)
        x, y = CX + rx * math.cos(a), WL + 10 + ry * math.sin(a)
        L = R.uniform(70, 220) * (0.6 + 0.6 * (y - WL) / 200)
        ripple("water_paint", x, y, L, R.uniform(5, 14), WATER, brush="flat", wet=0.85, sample_all=True, opacity=0.9)
        n += 1
    print("rim drags", n)

with doc.batch("ripples cut and spill", author=A):
    doc.add_layer("water_light", below="near", mode="screen")
    dark = light = 0
    for i in range(520):  # dark ripples inside the light: water between the wavelets
        y = WL + 8 + (R.random() ** 1.3) * 300
        half = 330 * (1 - ((y - WL) / 360) ** 2) ** 0.5 * R.uniform(0.7, 1.15)
        x = CX + R.uniform(-half, half)
        sz = 2 + 6 * (y - WL) / 300
        c = mix(WATER, (0.05, 0.06, 0.10), R.uniform(0, 0.6))
        ripple("water_paint", x, y, R.uniform(15, 90) * (0.5 + (y - WL) / 300), sz * R.uniform(0.7, 1.3), c,
               brush=R.choice(("flat", "bristle")), opacity=R.uniform(0.5, 0.9), color_jitter=0.1)
        dark += 1
    for i in range(420):  # warm wavelets: dense in the light, thinning out past the old rim
        y = WL + 6 + (R.random() ** 1.1) * 360
        spread = 330 * R.uniform(0.3, 1.45)
        x = CX + R.gauss(0, spread * 0.5)
        k = max(0.0, 1 - abs(x - CX) / 520) * max(0.15, 1 - (y - WL) / 380)
        c = mix(SKY_GLOW, SKY_HOT, R.random() * k)
        ripple("water_light", x, y, R.uniform(10, 70) * (0.5 + (y - WL) / 300), (1.5 + 5 * (y - WL) / 360) * R.uniform(0.7, 1.4),
               tuple(v * (0.25 + 0.6 * k) for v in c), brush=R.choice(("flat", "line", "bristle")),
               opacity=R.uniform(0.5, 1.0), color_jitter=0.15, hue_jitter=5)
        light += 1
    print("dark ripples", dark, "light ripples", light)

with doc.batch("bridge stone brushwork", author=A):
    doc.add_layer("stone", below="wall_r")
    br = doc.layer_pixels("bridge")
    ys, xs = np.nonzero(doc.mask_array("bridge") > 0.5)
    for i in range(380):
        j = R.randrange(len(xs))
        x, y = int(xs[j]), int(ys[j])
        c = br[y, x, :3]
        near_arch = math.hypot((x - CX) / 320, (y - WL) / 124)  # 1 on the arch rim
        warm = max(0, 1 - abs(near_arch - 1) * 3) * (1 if y > 560 else 0.4)
        c = mix(c, (0.62, 0.42, 0.36), warm * R.uniform(0.3, 0.7))
        c = tuple(min(1, v * R.uniform(0.8, 1.25)) for v in c)
        L = R.uniform(18, 60)
        if R.random() < 0.6:  # coursed stone: short horizontal blocks
            doc.stroke("stone", [(x, y, 1), (x + L, y + R.uniform(-1, 1), 1)], c, R.uniform(8, 16), brush="block",
                       mask="bridge", size_pressure=0, opacity=R.uniform(0.45, 0.85), color_jitter=0.1, grain=0.55,
                       seed=R.randrange(99999))
        else:
            doc.stroke("stone", curve((x, y), (x + L * 0.5, y + 2), (x + L, y), n=10, pressure=(0.5, 1, 0.2)), c,
                       R.uniform(10, 24), brush="chalk", mask="bridge", opacity=R.uniform(0.35, 0.7), grain=0.6,
                       seed=R.randrange(99999))
    for i in range(40):  # damp drips under the parapet and down the piers
        x = R.uniform(570, 1410)
        y = R.uniform(530, 560)
        doc.stroke("stone", curve((x, y), (x + 1, y + 30), (x, y + R.uniform(50, 110)), n=10, pressure=(1, 0.6, 0.05)),
                   (0.09, 0.08, 0.11), R.uniform(5, 12), brush="bristle", mask="bridge", opacity=0.5, grain=0.6,
                   seed=R.randrange(99999))
    print("stone strokes 420")

with doc.batch("arch glow and lost edge", author=A):
    for i in range(14):  # soft light spilling over the intrados, strongest at the crown
        a = math.pi * (0.15 + 0.7 * i / 13)
        x, y = CX + 300 * math.cos(a), WL - 112 * math.sin(a)
        doc.stroke("water_light", [(x, y, 1), (x, y + 1, 1)], (0.30, 0.17, 0.09), R.uniform(70, 120), brush="round",
                   hardness=0.0, opacity=0.55)
    rim = []
    for side in (-1, 1):  # warm rim light on the underside of the voussoirs, broken into dabs
        for i in range(18):
            a = math.pi / 2 + side * (math.pi / 2) * (0.05 + 0.9 * i / 17)
            x, y = CX + 322 * math.cos(a), WL - 126 * math.sin(a)
            if R.random() < 0.25:
                continue  # lost
            p = curve((x, y), (x + 6 * math.cos(a + side * 1.57), y - 2), (x + 14 * math.cos(a + side * 1.57), y - 4), n=6,
                      pressure=(0.6, 1, 0.3))
            rim.append(doc.stroke("water_light", p, (0.55, 0.33, 0.18), R.uniform(4, 8), brush="flat", opacity=0.8,
                                  seed=R.randrange(99999)))
    print("rim dab ids", rim[:3])
