# Clouds as banks, the near things (lamp, boat, washing line, pipes, quay edge), then light and air.
import math, random
from brush import curve
from _geo import *
from _windows import lit_windows

R = random.Random(6)
A = "agent:painter"
DARK = (0.06, 0.055, 0.085)

with doc.batch("cloud banks", author=A):
    doc.add_layer("clouds", below="glow")
    banks = [(520, 140, 760, 70), (1380, 80, 640, 55), (1010, 300, 520, 26), (1650, 250, 360, 30), (760, 30, 500, 40)]
    n = 0
    for cx, cy, wd, ht in banks:
        t = min(1, cy / 320)
        body = mix((0.19, 0.21, 0.35), (0.45, 0.37, 0.52), t)
        for k in range(int(wd / 18)):
            u = R.uniform(-1, 1)
            v = R.uniform(-1, 1)
            span = wd * (1 - abs(v) * 0.6) * R.uniform(0.25, 0.6)
            x = cx + u * wd * 0.5 * (1 - abs(v) * 0.5) - span / 2
            y = cy + v * ht * 0.5
            doc.stroke("clouds", curve((x, y), (x + span * 0.5, y - R.uniform(0, 6)), (x + span, y + R.uniform(-3, 3)), n=20,
                                       pressure=(0.15, 1, 0.1)), mix(body, SKY_MID, R.random() * 0.3), ht * R.uniform(0.25, 0.6),
                       brush="bristle", opacity=0.5, color_jitter=0.1, grain=0.4, seed=500 + n)
            n += 1
        for k in range(int(wd / 40)):  # the underside lit by the glow below the horizon
            x = cx + R.uniform(-0.45, 0.35) * wd
            y = cy + ht * R.uniform(0.25, 0.5)
            span = R.uniform(0.15, 0.4) * wd
            doc.stroke("clouds", curve((x, y), (x + span * 0.5, y - 2), (x + span, y + 1), n=16, pressure=(0.1, 1, 0.1)),
                       mix(SKY_GLOW, (0.95, 0.55, 0.60), R.random()), R.uniform(3, 8) * (0.6 + t), brush="flat",
                       opacity=0.4 + 0.45 * t, seed=700 + n)
            n += 1
    print("cloud strokes", n)

with doc.batch("near things", author=A):
    doc.add_layer("near")
    # pipes down the building joints
    for x0, y0, x1, y1 in ((1762, 0, 1762, 860), (258, 0, 258, 760)):
        doc.stroke("near", curve((x0, y0), (x1, y1), n=12), DARK, 9, brush="block", size_pressure=0, opacity=0.9)
        doc.stroke("near", curve((x0 + 3, y0), (x1 + 3, y1), n=12), (0.30, 0.27, 0.35), 2, brush="line", size_pressure=0, opacity=0.6)
    # the quay's lip catches the sky
    lip = doc.stroke("near", curve((0, 836), (620, left_y(836, 620)), n=30), (0.42, 0.40, 0.50), 4, brush="flat",
                     size_pressure=0, opacity=0.85, color_jitter=0.12, mask="!water", seed=31)
    print("quay lip id", lip)
    for x in (120, 470):  # bollards
        yb = left_y(812, x)
        s = 30 * (1000 - x) / 1000 + 6
        doc.stroke("near", curve((x, yb), (x, yb - s * 1.4), n=6), DARK, s, brush="block", size_pressure=0)
        doc.stroke("near", curve((x - s * 0.3, yb - s * 1.35), (x + s * 0.2, yb - s * 1.4), n=4), (0.35, 0.33, 0.42), 2.5, brush="line")
    # washing line across the canal, sagging, a few cloths against the glow
    line = curve((262, 236), (900, 312), (1500, 286), (1760, 236), n=60)
    lid = doc.stroke("near", line, (0.08, 0.07, 0.10), 2, brush="line", size_pressure=0)
    print("washing line id", lid)
    for i in range(4, 56, 6):
        x, y, _ = line[i]
        if R.random() < 0.3:
            continue
        w, h = R.uniform(14, 34), R.uniform(24, 60)
        col = R.choice([(0.55, 0.28, 0.30), (0.62, 0.55, 0.52), (0.28, 0.33, 0.45), (0.50, 0.42, 0.30)])
        doc.stroke("near", curve((x + w / 2, y), (x + w / 2 + R.uniform(-3, 3), y + h), n=8), col, w, brush="block",
                   size_pressure=0, color_jitter=0.12, seed=900 + i)
    # lamp post on the quay
    LX, LB = 380, left_y(812, 380)
    doc.stroke("near", curve((LX, LB), (LX, 330), n=20), DARK, 11, brush="block", size_pressure=0)
    doc.stroke("near", curve((LX - 9, LB), (LX + 9, LB), n=4), DARK, 14, brush="block", size_pressure=0)
    doc.stroke("near", curve((LX - 14, 300), (LX + 14, 300), n=4), DARK, 8, brush="block", size_pressure=0)
    lamp = doc.stroke("near", curve((LX, 304), (LX, 334), n=6), (1.0, 0.86, 0.6), 18, brush="block", size_pressure=0)
    doc.stroke("near", curve((LX - 10, 296), (LX + 10, 296), n=4), DARK, 4, brush="line")
    print("lamp glass id", lamp)
    # moored boat by the right wall
    doc.mask_polygon("boat", [(1490, 787), (1920, 925), (1920, 1012), (1530, 826)], feather=0.8)
    doc.fill("near", (0.07, 0.065, 0.095), mask="boat")
    doc.gradient("near", (1500, 0), (1920, 0), (0.14, 0.10, 0.13), (0.06, 0.055, 0.08), mask="boat", opacity=0.8)
    gun = doc.stroke("near", curve((1492, 787), (1920, 926), n=30), mix(SKY_GLOW, (0.45, 0.35, 0.40), 0.35), 4,
                     brush="flat", size_pressure=0, opacity=0.9, seed=41)
    print("gunwale id", gun)
    doc.mask_polygon("cabin", [(1690, right_y(800, 1690)), (1870, right_y(800, 1870)), (1870, right_y(930, 1870)), (1690, right_y(930, 1690))])
    doc.fill("near", (0.10, 0.085, 0.12), mask="cabin")
    doc.stroke("near", curve((1690, right_y(800, 1690)), (1870, right_y(800, 1870)), n=12), mix(SKY_GLOW, (0.4, 0.3, 0.4), 0.4),
               3, brush="flat", size_pressure=0, opacity=0.85)
    for x in (1730, 1800):
        doc.stroke("near", curve((x, right_y(830, x)), (x, right_y(880, x)), n=4), LAMP, 22, brush="block", size_pressure=0,
                   mask="cabin", color_jitter=0.1)
    doc.stroke("water", curve((1520, 840), (1920, 1030), n=20), (0.04, 0.04, 0.07), 40, brush="flat", size_pressure=0.3,
               opacity=0.7, mask="water", seed=42)

with doc.batch("light", author=A):
    doc.add_layer("light", mode="screen")
    lr, ll = lit_windows()
    for cx, ya, yb, w in lr + ll:
        cy = (ya + yb) / 2
        doc.gradient("light", (cx, cy), (cx, cy + (yb - ya) * 0.9), (0.30, 0.16, 0.06), (0, 0, 0), shape="radial")
    doc.gradient("light", (380, 318), (380, 318 + 170), (0.55, 0.36, 0.15), (0, 0, 0), shape="radial")
    doc.gradient("light", (380, 600), (380, 600 + 330), (0.16, 0.10, 0.05), (0, 0, 0), shape="radial")
    doc.gradient("light", (1760, 870), (1760, 870 + 120), (0.22, 0.12, 0.05), (0, 0, 0), shape="radial")
    # air: the far end of the canal is full of glowing haze
    doc.gradient("light", (985, 600), (985, 600 + 520), (0.24, 0.14, 0.09), (0, 0, 0), shape="radial")

with doc.batch("vignette", author=A):
    doc.add_layer("shade", mode="multiply")
    doc.gradient("shade", (985, 560), (985, 560 + 1150), (1, 1, 1), (0.45, 0.45, 0.62), shape="radial")
