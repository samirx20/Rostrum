import sys, time
sys.path.insert(0, r"C:\Users\Sam\.t3\worktrees\Rostrum\team-priyam\proofs\paint\kit")
import numpy as np
from PIL import Image, ImageDraw
from brush import curve, TIPS
from doc import Doc

CW, RH, X0, Y0 = 250, 140, 110, 40
cols = ["even p=1", "taper", "small 10/3px", "wet 0.5", "smudge wet=1", "grain 0.5"]
W, H = X0 + CW * len(cols), Y0 + RH * (len(TIPS) + 1) + 10
d = Doc.new(W, H, background=(0.93, 0.91, 0.86), paper_seed=1)
d.add_layer("paint")
d.add_layer("over")
ink = (0.55, 0.22, 0.12)
t0 = time.time()
with d.batch("stripes under wet columns"):
    for r in range(len(TIPS) + 1):
        for ci in (3, 4):
            x = X0 + CW * ci
            for k, c in enumerate([(0.15, 0.3, 0.6), (0.95, 0.8, 0.2), (0.2, 0.55, 0.3)]):
                y = Y0 + RH * r + 25 + k * 30
                d.stroke("paint", [(x + 15, y), (x + CW - 15, y)], c, 26, brush="block", size_pressure=0, seed=k + 9)
for r, tip in enumerate(TIPS):
    y = Y0 + RH * r + 55
    with d.batch(f"row {tip}"):
        def S(ci, size, pr, **kw):
            x = X0 + CW * ci
            pts = curve((x + 20, y + 15), (x + CW / 2, y - 25), (x + CW - 20, y + 10), n=40, pressure=pr)
            d.stroke("paint", pts, ink, size, brush=tip, seed=r * 10 + ci, **kw)
        big = 6 if tip == "line" else 40
        S(0, big, (1, 1, 1), size_pressure=0)
        S(1, big, (0.1, 1, 0.05))
        x = X0 + CW * 2
        for k, sz in enumerate((10, 3)):
            d.stroke("paint", curve((x + 20, y - 20 + 40 * k), (x + CW - 20, y - 10 + 40 * k), pressure=(0.3, 1, 0.2)),
                     ink, sz, brush=tip, seed=r + k)
        S(3, big, (0.6, 1, 0.4), wet=0.5)
        S(4, big, (0.6, 1, 0.4), wet=1.0)
        S(5, big, (1, 1, 1), grain=0.5, size_pressure=0, opacity=0.8)
y = Y0 + RH * len(TIPS) + 55
with d.batch("extras"):
    x = X0
    for k, (hj, cj) in enumerate([(0, 0), (20, 0.0), (0, 0.2)]):
        d.stroke("paint", curve((x + 15, y - 40 + 35 * k), (x + 2 * CW - 30, y - 40 + 35 * k)), (0.2, 0.5, 0.7), 26,
                 brush="flat", hue_jitter=hj, color_jitter=cj, seed=k, size_pressure=0)
    x = X0 + CW * 2
    d.stroke("paint", curve((x + 20, y - 20), (x + CW - 20, y - 20)), ink, 30, brush="block", size_pressure=0, seed=5)
    d.stroke("paint", curve((x + 60, y - 50), (x + 80, y + 50)), (0.4, 0.5, 0.9), 40, brush="round",
             mode="multiply", opacity=0.7, hardness=0.3)
    d.add_layer("glaze", mode="multiply", opacity=0.6)
    d.stroke("glaze", curve((x + 150, y - 50), (x + 170, y + 50)), (0.4, 0.5, 0.9), 40, brush="round", hardness=0.3)
    x3 = X0 + CW * 3
    d.stroke("paint", curve((x3 + 120, y - 50), (x3 + 120, y + 50)), (0, 0, 0), 24, brush="block", mode="erase",
             size_pressure=0)
    d.stroke("over", curve((X0 + CW * 4 + 20, y + 20), (X0 + CW * 5 - 20, y - 20)), (0, 0, 0), 30, brush="round",
             wet=1.0, sample_all=True)
    d.fill("over", (0.1, 0.1, 0.1), mask=d.mask_polygon("sq", [(X0 + CW * 5 + 30, y - 50), (X0 + CW * 6 - 30, y - 50),
                                                             (X0 + CW * 6 - 30, y + 50), (X0 + CW * 5 + 30, y + 50)]), opacity=0.3)
print(f"painted in {time.time() - t0:.1f}s, {len(d.s.info)} ops")
out = sys.argv[1]
d.export_png(out)
im = Image.open(out); g = ImageDraw.Draw(im)
for ci, c in enumerate(cols):
    g.text((X0 + CW * ci + 10, 10), c, fill=(0, 0, 0))
for r, tip in enumerate(TIPS):
    g.text((10, Y0 + RH * r + 50), tip, fill=(0, 0, 0))
yl = Y0 + RH * len(TIPS) + 5
for ci, c in enumerate(["flat: plain / hue_jitter 20 / color_jitter .2", "", "mode=multiply | glaze layer",
                        "erase (block)", "wet=1 sample_all, empty layer", "fill + mask, 30%"]):
    g.text((X0 + CW * ci + 10, yl), c, fill=(0, 0, 0))
im.save(out)
