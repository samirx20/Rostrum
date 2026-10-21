# Block-in: big value / colour shapes on their own layers. One light: the last glow at the canal's far end.
import math
from _geo import *

for name in ("sky", "far", "bridge", "wall_r", "wall_l", "water"):
    doc.add_layer(name)

# --- shapes --------------------------------------------------------------------------------
right = [(1920, 1760, -300), (1760, 1620, -100), (1620, 1500, 50), (1500, 1400, -150), (1400, 1340, 120)]
pts = []
for xn, xf, y0 in right:
    pts += [(xn, max(-5, right_y(y0, xn))), (xf, max(-5, right_y(y0, xf)))]
pts += [(1340, right_y(880, 1340)), (1920, 880)]
doc.mask_polygon("wall_r", [(1920, -5)] + pts)

left = [(0, 260, -300), (260, 460, -50), (460, 620, 110)]
pts = []
for xn, xf, y0 in left:
    pts += [(xn, max(-5, left_y(y0, xn))), (xf, max(-5, left_y(y0, xf)))]
pts += [(620, left_y(790, 620)), (0, 790)]
doc.mask_polygon("wall_l", [(0, -5)] + pts)
doc.mask_polygon("quay_top", [(0, 790), (620, left_y(790, 620)), (620, left_y(835, 620)), (0, 835)])
doc.mask_polygon("quay_face", [(0, 835), (620, left_y(835, 620)), (620, left_y(880, 620)), (0, 880)])

arch = [(980 + 320 * math.cos(a), 712 - 124 * math.sin(a)) for a in [i * math.pi / 40 for i in range(41)]]
doc.mask_polygon("bridge", [(560, 498), (1420, 498), (1420, 712)] + arch + [(560, 712)])
doc.mask_polygon("arch", [(660, 712)] + arch[::-1])
doc.mask_polygon("water", [(0, 880), (620, left_y(880, 620)), (1340, right_y(880, 1340)), (1920, 880), (1920, 1080), (0, 1080)])
# far city skyline behind the bridge, irregular roofs and a tower
sky_pts = [(540, 640), (540, 430), (600, 430), (600, 452), (660, 452), (660, 418), (700, 405), (740, 418),
           (740, 440), (800, 440), (800, 395), (812, 395), (812, 372), (824, 372), (824, 395), (860, 395),
           (860, 448), (930, 448), (930, 425), (990, 425), (990, 455), (1050, 455), (1050, 300), (1062, 288),
           (1074, 300), (1074, 360), (1100, 360), (1100, 432), (1160, 432), (1160, 410), (1215, 410),
           (1215, 444), (1280, 444), (1280, 400), (1300, 385), (1320, 400), (1320, 450), (1440, 450), (1440, 640)]
doc.mask_polygon("far", sky_pts)

# --- paint ---------------------------------------------------------------------------------
with doc.batch("sky values", author="agent:painter"):
    doc.gradient("sky", (0, 0), (0, 330), SKY_TOP, SKY_MID)
    doc.gradient("sky", (0, 300), (0, 600), SKY_MID, SKY_GLOW, mask=None, opacity=1.0)
    doc.gradient("sky", (0, 0), (0, 300), SKY_TOP, SKY_MID, mask=None, opacity=1.0)
    doc.gradient("sky", (1010, 520), (1500, 520), SKY_HOT, SKY_GLOW, shape="radial", opacity=0.75)
with doc.batch("far city", author="agent:painter"):
    doc.fill("far", FAR, mask="far")
    doc.gradient("far", (0, 380), (0, 640), (0.42, 0.34, 0.46), (0.70, 0.50, 0.46), mask="far")
with doc.batch("bridge mass", author="agent:painter"):
    doc.fill("bridge", BRIDGE, mask="bridge")
with doc.batch("walls mass", author="agent:painter"):
    doc.gradient("wall_r", (1920, 0), (1340, 0), (0.19, 0.17, 0.25), (0.30, 0.25, 0.30), mask="wall_r")
    doc.gradient("wall_l", (0, 0), (620, 0), (0.13, 0.13, 0.20), (0.27, 0.23, 0.29), mask="wall_l")
    doc.fill("wall_l", (0.30, 0.28, 0.34), mask="quay_top")
    doc.fill("wall_l", (0.10, 0.10, 0.15), mask="quay_face")
with doc.batch("water mass", author="agent:painter"):
    doc.gradient("water", (0, 700), (0, 1080), (0.55, 0.42, 0.45), WATER, mask="water")
    doc.gradient("water", (1000, 720), (1000, 1080), SKY_GLOW, WATER, mask="water", opacity=0.6)
