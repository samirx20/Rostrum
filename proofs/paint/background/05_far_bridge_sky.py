# Far city in haze, the canal continuing through the arch, bridge stone and rim light, clouds lit from below.
import math, random
from brush import curve
from _geo import *

R = random.Random(5)
A = "agent:painter"
HAZE = (0.78, 0.58, 0.52)

with doc.batch("far city haze", author=A):
    doc.gradient("far", (0, 300), (0, 500), (0.47, 0.40, 0.55), mix(FAR, HAZE, 0.8), mask="far")
    # second, nearer row of roofs: darker, lower
    doc.mask_polygon("far2", [(540, 520), (540, 470), (610, 470), (630, 455), (650, 470), (720, 470), (720, 462),
                              (770, 462), (770, 476), (880, 476), (880, 466), (905, 450), (930, 466), (1130, 466),
                              (1130, 455), (1180, 455), (1180, 470), (1250, 470), (1250, 458), (1300, 458),
                              (1300, 474), (1440, 474), (1440, 520)])
    doc.fill("far", (0.36, 0.29, 0.38), mask="far2")
    doc.gradient("far", (0, 455), (0, 500), (0.40, 0.31, 0.38), mix((0.36, 0.29, 0.38), HAZE, 0.5), mask="far2")
    for k in range(40):  # tiny lit windows in the far city
        x, y = R.uniform(560, 1420), R.uniform(470, 495)
        doc.stroke("far", [(x, y, 1), (x, y + 3, 1)], mix(LAMP, SKY_HOT, R.random()), 2.2, brush="block",
                   size_pressure=0, mask="far2", opacity=0.9, seed=k)
    for k in range(10):  # chimneys and masts on the skyline
        x = R.uniform(580, 1400)
        top = R.uniform(395, 440)
        doc.stroke("far", curve((x, 470), (x, top), n=6), (0.42, 0.35, 0.47), R.uniform(2, 6), brush="block",
                   size_pressure=0, opacity=0.9, seed=k + 50)

with doc.batch("through the arch", author=A):
    # the canal goes on: far wall wedges converging, a far bridge, glow on the water
    doc.mask_polygon("far_canal_l", [(640, 600), (900, 618), (900, 660), (640, 712)])
    doc.mask_polygon("far_canal_r", [(1320, 596), (1070, 616), (1070, 660), (1320, 712)])
    doc.fill("far", (0.45, 0.33, 0.38), mask="far_canal_l")
    doc.fill("far", (0.50, 0.37, 0.40), mask="far_canal_r")
    doc.mask_polygon("far_bridge", [(900, 630), (1070, 630), (1070, 646), (900, 646)])
    doc.fill("far", (0.55, 0.40, 0.42), mask="far_bridge")
    doc.mask_polygon("far_water", [(640, 712), (900, 660), (1070, 660), (1320, 712)])
    doc.gradient("far", (985, 650), (985, 712), SKY_HOT, mix(SKY_GLOW, (0.4, 0.3, 0.35), 0.4), mask="far_water")
    for k in range(18):
        x, y = R.uniform(660, 1300), R.uniform(605, 650)
        doc.stroke("far", [(x, y, 1), (x, y + 5, 1)], LAMP, 3, brush="block", size_pressure=0, mask="far_canal_l" if x < 985 else "far_canal_r", seed=k + 90)

with doc.batch("bridge stone", author=A):
    doc.fill_region("bridge", "bridge", (0.27, 0.22, 0.27), 26, angle=0, gap=1.3, length=3, brush="chalk",
                    opacity=0.35, grain=0.6, color_jitter=0.2, seed=11)
    doc.gradient("bridge", (0, 498), (0, 712), (0.24, 0.19, 0.24), (0.10, 0.08, 0.12), mask="bridge", opacity=0.55)
    # voussoirs: wedge stones radiating round the arch
    ring = []
    for i in range(23):
        a = math.pi * (i + 0.5) / 23
        ca, sa = math.cos(a), math.sin(a)
        p0 = (980 + 320 * ca, 712 - 124 * sa)
        p1 = (980 + 368 * ca, 712 - 160 * sa)
        col = mix((0.30, 0.24, 0.28), (0.16, 0.13, 0.17), R.random())
        ring.append(doc.stroke("bridge", curve(p0, p1, n=6), col, 26, brush="block", size_pressure=0,
                               mask="bridge", color_jitter=0.15, grain=0.4, seed=200 + i))
        doc.stroke("bridge", curve(p0, p1, n=6), (0.08, 0.06, 0.09), 2, brush="line", size_pressure=0, mask="bridge",
                   angle=None, opacity=0.6)
    print("voussoir ids", ring[0], "..", ring[-1])
    # the arch's inner lip catches the glow
    lip = [(980 + 322 * math.cos(a), 712 - 126 * math.sin(a), 1) for a in [math.pi * i / 60 for i in range(61)]]
    lip_id = doc.stroke("bridge", lip, mix(SKY_GLOW, (0.4, 0.3, 0.3), 0.3), 4, brush="flat", size_pressure=0,
                        mask="bridge", opacity=0.85, seed=7)
    print("arch lip id", lip_id)

with doc.batch("bridge parapet", author=A):
    rim = doc.stroke("bridge", curve((560, 500), (1420, 500), n=40), mix(SKY_GLOW, (0.5, 0.4, 0.4), 0.2), 5, brush="flat",
                     size_pressure=0, opacity=0.9, color_jitter=0.15, seed=8)
    print("parapet rim id", rim)
    doc.stroke("bridge", curve((560, 512), (1420, 512), n=40), (0.12, 0.09, 0.13), 6, brush="block", size_pressure=0, opacity=0.8)
    # railing posts against the glow, and two lamps
    for x in range(570, 1420, 22):
        doc.stroke("bridge", curve((x, 498), (x, 474), n=4), (0.15, 0.11, 0.15), 3, brush="block", size_pressure=0)
    doc.stroke("bridge", curve((560, 476), (1420, 476), n=40), (0.15, 0.11, 0.15), 3, brush="line", size_pressure=0)
    for x in (700, 1260):
        doc.stroke("bridge", curve((x, 498), (x, 420), n=8), (0.12, 0.09, 0.12), 5, brush="block", size_pressure=0)
        doc.stroke("bridge", [(x, 418, 1), (x, 412, 1)], (1.0, 0.85, 0.6), 9, brush="round", hardness=0.6)

with doc.batch("clouds", author=A):
    doc.add_layer("clouds", below="glow")
    for k in range(70):
        y = R.uniform(40, 330)
        t = y / 330
        x = R.uniform(150, 1700)
        ln = R.uniform(120, 420)
        body = mix((0.20, 0.22, 0.36), (0.42, 0.36, 0.52), t)
        doc.stroke("clouds", curve((x, y), (x + ln * 0.5, y - R.uniform(2, 10)), (x + ln, y + R.uniform(-4, 4)), n=24,
                                   pressure=(0.2, 1, 0.1)), body, R.uniform(14, 40) * (0.6 + t), brush="bristle",
                   opacity=0.55, color_jitter=0.12, grain=0.4, seed=300 + k)
        # underside caught by the low sun
        doc.stroke("clouds", curve((x + ln * 0.1, y + 8), (x + ln * 0.6, y + 6), (x + ln * 0.9, y + 10), n=20,
                                   pressure=(0.1, 1, 0.1)), mix(SKY_GLOW, (0.9, 0.5, 0.55), R.random()), R.uniform(3, 9),
                   brush="flat", opacity=0.45 + 0.4 * t, seed=400 + k)
