# Round 2, surface pass 4: near-wall detail placed from the real window strokes (asked from the document, not
# guessed: the first try put shutters in the wrong place), the arch crown glow, and the lower rim of the water
# light broken with long dark and warm ripples so it no longer reads as an oval.
import math, random
from brush import curve
from _geo import *

R = random.Random(114)
A = "agent:painter2"
CX, WL = 980, 712


def jit(c, k=0.12):
    return tuple(min(1, max(0, v * R.uniform(1 - k, 1 + k))) for v in c)


wins = []  # (x, y top, y bottom, width, mask) of every window pane block on the facade layer
for sid in range(2406, 2574):
    o = doc.stroke_info(sid)
    if o["brush"] == "block" and o["mask"] in ("bl0", "bl1", "br0", "br1"):
        xs = [p[0] for p in o["points"]]; ys = [p[1] for p in o["points"]]
        wins.append((sum(xs) / len(xs), min(ys), max(ys), o["size"], o["mask"]))
print("windows found", len(wins))

with doc.batch("near wall detail", author=A):
    doc.add_layer("detail", below="wall_air")
    ids = []
    for x, ya, yb, w, m in wins:  # shutters both sides, the one toward the vanishing point narrower
        left = m.startswith("bl")
        for side in (-1, 1):
            toward_vp = (side == 1) == left
            sw = w * (0.42 if toward_vp else 0.6)
            sx = x + side * (w / 2 + sw / 2 + 1)
            c = jit((0.14, 0.17, 0.21), 0.18)
            ids.append(doc.stroke("detail", [(sx, ya - 2, 1), (sx, yb + 2, 1)], c, sw, brush="block", mask=m,
                                  size_pressure=0, opacity=0.8, color_jitter=0.15, grain=0.55, seed=R.randrange(99999)))
            if w > 16:
                for k in range(int((yb - ya) / 22)):  # louvres
                    yy = ya + 10 + k * 22
                    doc.stroke("detail", [(sx - sw / 2 + 2, yy, 1), (sx + sw / 2 - 2, yy + 1, 1)], (0.07, 0.08, 0.11), 2,
                               brush="line", mask=m, opacity=0.6)
        doc.stroke("detail", [(x - w / 2 - 3, ya - 6, 1), (x + w / 2 + 3, ya - 6, 1)], (0.09, 0.09, 0.13), max(3, w * 0.18),
                   brush="flat", mask=m, size_pressure=0, opacity=0.7, seed=R.randrange(99999))  # lintel shadow
    for x, m, top in ((1752, "br0", 60), (1905, "br0", -5), (250, "bl0", 120), (452, "bl1", 290), (608, "bl2", 470)):
        yb = 880 if m.startswith("br") else 790
        ids.append(doc.stroke("detail", [(x, top, 1), (x + 1, (top + yb) / 2, 1), (x, yb, 1)], (0.06, 0.06, 0.09), 9,
                              brush="flat", size_pressure=0, mask=m, grain=0.3, seed=R.randrange(99999)))
        side = -4 if m.startswith("br") else 4
        doc.stroke("detail", [(x + side, top, 0.6), (x + side, yb, 1)], (0.55, 0.38, 0.33), 2.5, brush="line", mask=m,
                   opacity=0.55)
        for y in range(int(top) + 60, yb, 140):
            doc.stroke("detail", [(x - 8, y, 1), (x + 8, y, 1)], (0.04, 0.04, 0.06), 4, brush="block", size_pressure=0, mask=m)
    for x, m, y0, y1 in ((1620, "br2", right_y(50, 1620), 870), (1500, "br3", right_y(-150, 1500), 870),
                         (1400, "br4", right_y(120, 1400), 870), (460, "bl2", left_y(110, 460), 790),
                         (260, "bl1", left_y(-50, 260), 790)):  # broken warm line on corners turning to the glow
        y = max(0, y0)
        while y < y1:
            L = R.uniform(40, 160)
            if R.random() < 0.7:
                ids.append(doc.stroke("detail", [(x + 2, y, 0.5), (x + 2, min(y1, y + L), 1)], (0.66, 0.46, 0.38),
                                      R.uniform(3, 6), brush="flat", mask=m, opacity=R.uniform(0.5, 0.9), seed=R.randrange(99999)))
            y += L + R.uniform(10, 60)
    for x, y0 in ((1440, -150), (1470, -150), (1560, 50), (1590, 50), (1680, -100), (1720, -100)):  # chimney pots
        yb = right_y(y0, x) + 4
        h = R.uniform(18, 34)
        doc.stroke("detail", [(x, yb, 1), (x, yb - h, 1)], (0.13, 0.12, 0.17), R.uniform(10, 16), brush="block",
                   size_pressure=0, grain=0.4, seed=R.randrange(99999))
        doc.stroke("detail", [(x - 8, yb - h, 1), (x + 8, yb - h, 1)], (0.42, 0.33, 0.38), 3, brush="block", size_pressure=0)
    print("shutter / pipe / edge ids", ids[:2], ids[-2:])

with doc.batch("arch crown glow", author=A):
    for i in range(9):
        a = math.pi * (0.2 + 0.6 * i / 8)
        x, y = CX + 290 * math.cos(a), WL - 105 * math.sin(a)
        doc.stroke("water_light", [(x, y, 1), (x, y + 1, 1)], (0.26, 0.15, 0.08), 110, brush="round", hardness=0.0, opacity=0.5)

with doc.batch("water rim broken", author=A):
    rim = []
    for i in range(140):  # long dark ripples crossing the lower and side rim of the light
        a = R.uniform(0.05, math.pi - 0.05)
        x, y = CX + 340 * math.cos(a) * R.uniform(0.8, 1.1), WL + 10 + 120 * math.sin(a) * R.uniform(0.85, 1.15)
        L = R.uniform(80, 260)
        p = curve((x - L / 2, y), (x, y + R.uniform(-2, 2)), (x + L / 2, y), n=12, pressure=(0.2, 1, 0.2))
        rim.append(doc.stroke("water_paint", p, jit(mix(WATER, (0.05, 0.06, 0.1), 0.4)), R.uniform(4, 11),
                              brush=R.choice(("flat", "bristle")), opacity=R.uniform(0.6, 0.95), seed=R.randrange(99999)))
    for i in range(160):  # warm streaks under the arch base and spilling below the old rim
        y = WL + 4 + R.random() ** 1.6 * 260
        x = CX + R.gauss(0, 200 + (y - WL))
        L = R.uniform(40, 200) * (1 - (y - WL) / 400)
        k = max(0.1, 1 - (y - WL) / 260)
        c = tuple(v * (0.25 + 0.55 * k) for v in mix(SKY_GLOW, SKY_HOT, k))
        doc.stroke("water_light", curve((x - L / 2, y), (x, y), (x + L / 2, y), n=10, pressure=(0.1, 1, 0.1)), c,
                   R.uniform(2, 6), brush=R.choice(("flat", "line")), opacity=R.uniform(0.5, 1.0), seed=R.randrange(99999))
    print("rim ripple ids", rim[:2])
