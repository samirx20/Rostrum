# Light and air, take two: glows as soft airbrush dabs (a gradient covers the whole layer, so it can't stack),
# warm bounce on the walls near the glow, cool on the near walls, then the vignette.
import random
from brush import curve
from _geo import *
from _windows import lit_windows

R = random.Random(7)
A = "agent:painter"

with doc.batch("wall air", author=A):
    doc.add_layer("wall_air", below="water")
    for m, col, op in (("br2", SKY_GLOW, 0.22), ("br3", SKY_GLOW, 0.25), ("br4", SKY_GLOW, 0.32), ("bl2", SKY_GLOW, 0.30),
                       ("bl1", (0.75, 0.48, 0.42), 0.15), ("br1", (0.45, 0.42, 0.62), 0.14), ("br0", (0.45, 0.40, 0.60), 0.12),
                       ("bl0", (0.30, 0.30, 0.48), 0.12)):
        doc.fill_region("wall_air", m, col, 34, angle=90, gap=1.1, length=4, brush="bristle", opacity=op,
                        grain=0.5, color_jitter=0.2, hue_jitter=6, seed=R.randrange(9999))
    for m in ("br0", "br1", "bl0", "bl1"):  # damp stains rising from the water
        doc.fill_region("wall_air", m, (0.05, 0.06, 0.08), 22, angle=92, gap=2.2, length=3, brush="chalk",
                        opacity=0.25, grain=0.7, pressure=(1, 0.6, 0.1), seed=R.randrange(9999))

with doc.batch("glows", author=A):
    doc.add_layer("light", mode="screen")
    lr, ll = lit_windows()
    for cx, ya, yb, w in lr + ll:
        cy = (ya + yb) / 2
        doc.stroke("light", [(cx, cy, 1), (cx, cy + 1, 1)], (0.42, 0.24, 0.09), (yb - ya) * 1.6, brush="round",
                   hardness=0.05, opacity=0.6)
    lamp = doc.stroke("light", [(380, 318, 1), (380, 319, 1)], (0.75, 0.50, 0.22), 320, brush="round", hardness=0.0, opacity=0.8)
    doc.stroke("light", [(380, 318, 1), (380, 319, 1)], (1.0, 0.85, 0.55), 60, brush="round", hardness=0.2, opacity=0.8)
    doc.stroke("light", [(380, 640, 1), (380, 641, 1)], (0.30, 0.18, 0.08), 600, brush="round", hardness=0.0, opacity=0.6)
    doc.stroke("light", [(1765, 870, 1), (1765, 871, 1)], (0.40, 0.22, 0.08), 260, brush="round", hardness=0.0, opacity=0.6)
    for x in (700, 1260):
        doc.stroke("light", [(x, 415, 1), (x, 416, 1)], (0.6, 0.4, 0.2), 90, brush="round", hardness=0.0, opacity=0.7)
    haze = doc.stroke("light", [(985, 600, 1), (985, 601, 1)], (0.30, 0.18, 0.11), 1000, brush="round", hardness=0.0, opacity=0.8)
    print("lamp glow id", lamp, "haze id", haze)

with doc.batch("vignette", author=A):
    doc.add_layer("shade", mode="multiply")
    doc.gradient("shade", (985, 560), (985, 560 + 1150), (1, 1, 1), (0.45, 0.45, 0.62), shape="radial")
