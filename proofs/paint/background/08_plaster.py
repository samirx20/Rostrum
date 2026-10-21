# Round 2, surface pass 1: hand-painted plaster on every building, then the windows, sills and cornices
# re-laid on top so the brushwork never buries them. Strokes follow the wall planes (toward the vanishing point)
# or hang vertical (rain streaks); colours are picked off the wall itself, then pushed warm / cool / light / dark.
import math, random
import numpy as np
from brush import curve
from _geo import *

R = random.Random(81)
A = "agent:painter2"
WALL = {m: ("wall_r" if m.startswith("br") else "wall_l") for m in ("br0", "br1", "br2", "br3", "br4", "bl0", "bl1", "bl2")}
COUNT = {"br0": 170, "br1": 120, "br2": 80, "br3": 60, "br4": 40, "bl0": 190, "bl1": 120, "bl2": 70}
WARM, COOL, DAMP = (0.52, 0.36, 0.33), (0.26, 0.28, 0.42), (0.07, 0.08, 0.11)
px = {n: doc.layer_pixels(n) for n in ("wall_r", "wall_l")}


def pick(m, n):
    ys, xs = np.nonzero(doc.mask_array(m) > 0.5)
    idx = [R.randrange(len(xs)) for _ in range(n)]
    return [(int(xs[i]), int(ys[i])) for i in idx], (xs.min(), xs.max(), ys.min(), ys.max())


def along(x, y):  # unit direction along the wall plane at (x, y): toward the vanishing point
    dx, dy = VP[0] - x, VP[1] - y
    d = math.hypot(dx, dy) or 1
    return dx / d, dy / d


def colour(m, x, y, box):
    c = px[WALL[m]][y, x, :3]
    x0, x1, y0, y1 = box
    far_t = abs(x - (1000)) / 920  # 0 at the far end (near the glow), 1 at the frame edge
    up = (y - y0) / max(1, y1 - y0)  # 0 at the roof, 1 at the water
    c = mix(c, WARM, R.uniform(0.0, 0.45) * (1.1 - far_t))  # warm bounce from the glow
    if R.random() < 0.35:
        c = mix(c, COOL, R.uniform(0.15, 0.4) * (1 - up))  # sky-lit, cool toward the roofs
    if up > 0.75 and R.random() < 0.5:
        c = mix(c, DAMP, R.uniform(0.2, 0.5))
    k = R.uniform(0.82, 1.22)
    return tuple(min(1, v * k) for v in c)


with doc.batch("plaster brushwork", author=A):
    doc.add_layer("plaster", below="wall_air")
    n = 0
    for m, cnt in COUNT.items():
        pts, box = pick(m, cnt)
        near = 1 - abs(pts[0][0] - 1000) / 1000
        for x, y in pts:
            c = colour(m, x, y, box)
            scale = 0.4 + 0.9 * abs(x - 1000) / 920  # strokes shrink with distance
            kind = R.random()
            if kind < 0.55:  # along the plane: flat / bristle
                ux, uy = along(x, y)
                L = R.uniform(60, 220) * scale
                bend = R.uniform(-6, 6)
                p = curve((x - ux * L / 2, y - uy * L / 2), (x + bend, y + bend * 0.3), (x + ux * L / 2, y + uy * L / 2),
                          n=16, pressure=(R.uniform(0.4, 0.9), 1, R.uniform(0.2, 0.6)))
                doc.stroke("plaster", p, c, R.uniform(14, 42) * scale, brush=R.choice(("flat", "bristle", "flat")),
                           mask=m, opacity=R.uniform(0.45, 0.85), color_jitter=0.12, hue_jitter=4, grain=0.45,
                           wet=R.choice((0, 0, 0.35)), seed=R.randrange(99999))
            elif kind < 0.8:  # rain streaks
                L = R.uniform(50, 200) * scale
                p = curve((x, y), (x + R.uniform(-3, 3), y + L / 2), (x + R.uniform(-4, 4), y + L), n=12,
                          pressure=(1, 0.7, 0.1))
                doc.stroke("plaster", p, c, R.uniform(8, 26) * scale, brush=R.choice(("chalk", "bristle")), mask=m,
                           opacity=R.uniform(0.35, 0.7), color_jitter=0.1, grain=0.6, seed=R.randrange(99999))
            else:  # broken plaster patches: short blocks on the plane
                ux, uy = along(x, y)
                L = R.uniform(25, 70) * scale
                p = [(x, y, 1), (x + ux * L, y + uy * L, 1)]
                doc.stroke("plaster", p, c, R.uniform(12, 30) * scale, brush="block", mask=m, size_pressure=0,
                           opacity=R.uniform(0.5, 0.9), color_jitter=0.08, grain=0.5, jitter=0.05, seed=R.randrange(99999))
            n += 1
    print("plaster strokes", n)

with doc.batch("facade re-laid", author=A):
    doc.add_layer("facade", below="wall_air")
    keep = 0
    for sid in range(58, 226):  # windows right / left, sills, cornices (batches 23-25)
        try:
            op = doc.stroke_info(sid)
        except KeyError:
            continue
        if op["op"] != "stroke":
            continue
        doc.stroke("facade", [tuple(p) for p in op["points"]], tuple(op["color"]), op["size"], brush=op["brush"],
                   mask=op["mask"], **op["params"])
        keep += 1
    print("facade strokes re-laid", keep)
