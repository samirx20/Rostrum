# Round 2, surface pass 6: the lit windows get frames, a hot core and curtains (found from the facade strokes
# by their colour), and the thin cloud dashes get painted masses with warm undersides lit by the glow.
import math, random
from brush import curve
from _geo import *

R = random.Random(136)
A = "agent:painter2"


def jit(c, k=0.1):
    return tuple(min(1, max(0, v * R.uniform(1 - k, 1 + k))) for v in c)


lit = []
for sid in range(2406, 2574):
    o = doc.stroke_info(sid)
    if o["brush"] == "block" and sum(o["color"]) > 1.3:
        xs = [p[0] for p in o["points"]]; ys = [p[1] for p in o["points"]]
        lit.append((sum(xs) / len(xs), min(ys), max(ys), o["size"], o["mask"]))
print("lit windows", len(lit))

with doc.batch("lit window detail", author=A):
    doc.add_layer("win_detail", below="wall_air")
    for x, ya, yb, w, m in lit:
        h = yb - ya
        doc.stroke("win_detail", [(x - w * 0.15, ya + h * 0.25, 1), (x - w * 0.1, yb - h * 0.15, 1)], (1.0, 0.86, 0.6),
                   w * 0.45, brush="flat", mask=m, opacity=0.7, seed=R.randrange(99999))  # hot core, off-centre
        side = R.choice((-1, 1))
        doc.stroke("win_detail", curve((x + side * w * 0.32, ya + 2), (x + side * w * 0.25, ya + h * 0.5), (x + side * w * 0.35, yb - 2), n=8),
                   (0.55, 0.28, 0.16), w * 0.32, brush="bristle", mask=m, opacity=0.8, seed=R.randrange(99999))  # curtain
        doc.stroke("win_detail", [(x, ya, 1), (x, yb, 1)], (0.18, 0.11, 0.08), max(1.2, w * 0.07), brush="line", mask=m)
        for t in (0.33, 0.66):
            doc.stroke("win_detail", [(x - w / 2, ya + h * t, 1), (x + w / 2, ya + h * t, 1)], (0.18, 0.11, 0.08),
                       max(1.2, w * 0.06), brush="line", mask=m)

with doc.batch("cloud masses", author=A):
    doc.add_layer("cloud_paint", below="glow")
    n = 0
    for cx, cy, wd in ((560, 160, 520), (900, 48, 420), (1350, 98, 520), (830, 306, 300), (250, 60, 300), (1700, 30, 260)):
        lowness = cy / 320  # clouds nearer the horizon catch more of the glow
        for i in range(30):
            x = cx + R.gauss(0, wd / 3.5)
            y = cy + R.gauss(0, 9) - (1 - abs(x - cx) / wd) * 10
            L = R.uniform(60, 180)
            body = jit(mix((0.20, 0.21, 0.36), (0.34, 0.30, 0.44), lowness), 0.08)
            doc.stroke("cloud_paint", curve((x - L / 2, y + 2), (x, y - R.uniform(0, 4)), (x + L / 2, y + 2), n=12,
                                            pressure=(0.2, 1, 0.2)), body, R.uniform(10, 24), brush=R.choice(("bristle", "flat")),
                       opacity=R.uniform(0.5, 0.85), color_jitter=0.06, grain=0.35, seed=R.randrange(99999))
            n += 1
            if R.random() < 0.55:  # warm underside, thinner, a little below
                c = jit(mix((0.55, 0.38, 0.45), SKY_GLOW, 0.3 + 0.5 * lowness), 0.08)
                doc.stroke("cloud_paint", curve((x - L * 0.4, y + 9), (x, y + 11), (x + L * 0.4, y + 9), n=10, pressure=(0.1, 1, 0.1)),
                           c, R.uniform(3, 7), brush=R.choice(("flat", "bristle")), opacity=R.uniform(0.5, 0.9),
                           seed=R.randrange(99999))
                n += 1
    print("cloud strokes", n)
