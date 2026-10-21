# Walls: each building its own tone, sky-lit tops, grime at the water, texture, windows, sills, cornices.
import random
from brush import curve
from _geo import *

R = random.Random(3)
A = "agent:painter"
# (near x, far x, roof y0, tone) ; right x = 1000 + 920/z, left x = 1000 - 1000/z
RIGHT = [(1920, 1760, -300, (0.28, 0.22, 0.24)), (1760, 1620, -100, (0.22, 0.21, 0.29)),
         (1620, 1500, 50, (0.33, 0.27, 0.29)), (1500, 1400, -150, (0.26, 0.23, 0.28)),
         (1400, 1340, 120, (0.34, 0.28, 0.31))]
LEFT = [(0, 260, -300, (0.16, 0.15, 0.21)), (260, 460, -50, (0.21, 0.18, 0.24)), (460, 620, 110, (0.27, 0.23, 0.28))]


def rz(x): return 920 / (x - 1000)
def lz(x): return 1000 / (1000 - x)


def building_masks(side):
    out = []
    for i, (xn, xf, y0, tone) in enumerate(RIGHT if side == "r" else LEFT):
        yf = right_y if side == "r" else left_y
        base = 880 if side == "r" else 790
        name = f"b{side}{i}"
        doc.mask_polygon(name, [(xn, max(-5, yf(y0, xn))), (xf, max(-5, yf(y0, xf))), (xf, yf(base, xf)), (xn, yf(base, xn))])
        out.append((name, xn, xf, y0, tone))
    return out


with doc.batch("building tones", author=A):
    BR, BL = building_masks("r"), building_masks("l")
    for (name, xn, xf, y0, tone), side in [(b, "r") for b in BR] + [(b, "l") for b in BL]:
        layer = "wall_" + side
        doc.fill(layer, tone, mask=name)
        top = max(0, (right_y if side == "r" else left_y)(y0, xf))
        doc.gradient(layer, (0, top), (0, top + 380), mix(tone, SKY_MID, 0.35), tone, mask=name, opacity=0.8)
        doc.gradient(layer, (0, 560), (0, 880), tone, mix(tone, (0.06, 0.07, 0.09), 0.6), mask=name, opacity=0.9)

with doc.batch("wall texture", author=A):
    n = 0
    for (name, xn, xf, y0, tone), side in [(b, "r") for b in BR] + [(b, "l") for b in BL]:
        layer = "wall_" + side
        sz = max(10, abs(xn - xf) / 5)
        doc.fill_region(layer, name, mix(tone, (0.55, 0.48, 0.50), 0.25), sz, angle=90, gap=1.4, length=5,
                        brush="chalk", opacity=0.35, grain=0.6, color_jitter=0.15, seed=R.randrange(9999))
        doc.fill_region(layer, name, mix(tone, (0.05, 0.05, 0.08), 0.4), sz * 0.7, angle=88, gap=2.0, length=6,
                        brush="flat", opacity=0.3, grain=0.5, color_jitter=0.1, seed=R.randrange(9999))
        n += 2
    print("texture regions", n)


def windows(side, blds, tops, height, depth_step, width):
    ids, lit = [], []
    for name, xn, xf, y0, tone in blds:
        z0, z1 = (rz(xn), rz(xf)) if side == "r" else (lz(xn) if xn > 0 else 1.0, lz(xf))
        z = z0 + depth_step * 0.6
        while z + width < z1 - depth_step * 0.25:
            for t in tops:
                if t < y0 + 90:
                    continue
                if side == "r":
                    xa, xb = 1000 + 920 / z, 1000 + 920 / (z + width)
                else:
                    xa, xb = 1000 - 1000 / z, 1000 - 1000 / (z + width)
                cx, w = (xa + xb) / 2, abs(xa - xb)
                ya, yb = 600 + (t - 600) / z, 600 + (t + height - 600) / z
                on = R.random() < 0.22
                col = mix(LAMP, (1.0, 0.55, 0.30), R.random() * 0.5) if on else mix((0.08, 0.09, 0.14), SKY_MID, R.random() * 0.25)
                sid = doc.stroke("wall_" + side, curve((cx, ya), (cx, yb), n=12), col, w, brush="block",
                                 size_pressure=0, color_jitter=0.08, grain=0.3, mask=name, seed=R.randrange(9999))
                ids.append(sid)
                if on:
                    lit.append((cx, ya, yb, w))
                # sill: a thin sky-lit ledge under the window
                doc.stroke("wall_" + side, curve((cx - w * 0.65, yb + 2 / z), (cx + w * 0.65, yb + 2 / z), n=6),
                           mix(tone, SKY_MID, 0.8), max(1.5, 7 / z), brush="line", size_pressure=0, mask=name)
            z += depth_step
    return ids, lit


with doc.batch("windows right", author=A):
    ids_r, lit_r = windows("r", BR, [130, 330, 530], 140, 0.085, 0.035)
    print("right windows", len(ids_r), "first", ids_r[:3], "lit", len(lit_r))
with doc.batch("windows left", author=A):
    ids_l, lit_l = windows("l", BL, [60, 280, 500], 160, 0.09, 0.035)
    print("left windows", len(ids_l), "first", ids_l[:3], "lit", len(lit_l))

with doc.batch("cornices", author=A):
    for (name, xn, xf, y0, tone), side in [(b, "r") for b in BR] + [(b, "l") for b in BL]:
        yf = right_y if side == "r" else left_y
        if yf(y0, xf) < 0:
            continue
        z = rz(xf) if side == "r" else lz(xf)
        sid = doc.stroke("wall_" + side, curve((xn, yf(y0, xn) + 4), (xf, yf(y0, xf) + 4 / z), n=24),
                         mix(tone, SKY_GLOW, 0.45), max(3, 16 / z), brush="flat", size_pressure=0.2, opacity=0.9,
                         color_jitter=0.1, grain=0.3, seed=R.randrange(999))
        print("cornice", name, sid)
