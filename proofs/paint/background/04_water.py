# Water: a mirror broken by ripples. Dark bridge reflection, the arch's glow mirrored, lit windows as streaks.
import math, random
from brush import curve
from _geo import *
from _windows import lit_windows

R = random.Random(4)
A = "agent:painter"
WL = 712  # water line at the bridge

with doc.batch("water base", author=A):
    doc.gradient("water", (0, 712), (0, 1080), (0.20, 0.17, 0.24), (0.07, 0.09, 0.15), mask="water")
    # the bridge mirrored: its deck band and its arch opening
    arch = [(980 + 320 * math.cos(a), WL + 124 * math.sin(a)) for a in [i * math.pi / 40 for i in range(41)]]
    doc.mask_polygon("arch_refl", [(660, WL)] + arch[::-1], feather=7)
    doc.mask_polygon("bridge_refl", [(600, WL), (1360, WL), (1330, 2 * WL - 498), (630, 2 * WL - 498)], feather=14)
    doc.fill("water", (0.11, 0.09, 0.13), mask="bridge_refl", opacity=0.85)
    doc.gradient("water", (980, WL), (980, WL + 124), SKY_HOT, SKY_GLOW, mask="arch_refl", opacity=0.55)

with doc.batch("ripples in the glow", author=A):
    # horizontal broken dashes: the mirrored glow torn into strips, wider apart nearer the viewer
    y, n = WL + 4, 0
    while y < WL + 240:
        t = (y - WL) / 240
        half = 340 * (1 - t * 0.4)
        x = 980 - half + R.uniform(0, 40)
        while x < 980 + half:
            ln = R.uniform(20, 110) * (1 + t)
            inside = y < WL + 124 * math.sqrt(max(0, 1 - ((x + ln / 2 - 980) / 320) ** 2))
            col = mix(SKY_GLOW, (0.12, 0.10, 0.15), 0.85) if inside else mix(SKY_GLOW, SKY_HOT, R.random())
            doc.stroke("water", curve((x, y), (x + ln, y + R.uniform(-1, 1)), n=8, pressure=(0.3, 1, 0.3)), col,
                       2 + 5 * t, brush="flat", size_pressure=0.7, opacity=0.75, color_jitter=0.1, grain=0.2,
                       mask="water", seed=R.randrange(9999))
            n += 1
            x += ln + R.uniform(10, 60) * (1 + t)
        y += 3 + 10 * t
    print("glow ripples", n)

with doc.batch("wall reflections", author=A):
    # the walls mirrored as dark wedges along each bank, soft toward the middle of the canal
    doc.mask_polygon("refl_r", [(1340, right_y(880, 1340)), (1920, 880), (1920, 1080), (1500, 1080)], feather=30)
    doc.mask_polygon("refl_l", [(620, left_y(880, 620)), (0, 880), (0, 1080), (420, 1080)], feather=30)
    doc.fill("water", (0.10, 0.09, 0.14), mask="refl_r", opacity=0.6)
    doc.fill("water", (0.06, 0.07, 0.11), mask="refl_l", opacity=0.7)

with doc.batch("window reflections", author=A):
    lr, ll = lit_windows()
    n = 0
    for side, wins in (("r", lr), ("l", ll)):
        for cx, ya, yb, w in wins:
            base = right_y(880, cx) if side == "r" else left_y(790, cx) + (left_y(880, cx) - left_y(790, cx))
            top, bot = 2 * base - yb, 2 * base - ya
            if side == "l":
                top, bot = base + 6, base + (yb - ya) * 1.3
            y = top
            while y < min(bot, 1075):
                ln = w * R.uniform(0.8, 2.2)
                doc.stroke("water", curve((cx - ln / 2 + R.uniform(-3, 3), y), (cx + ln / 2, y), n=6, pressure=(0.4, 1, 0.4)),
                           mix(LAMP, (1.0, 0.5, 0.25), R.random() * 0.6), max(1.5, w * 0.18), brush="flat",
                           opacity=0.8 * (1 - (y - top) / max(1, bot - top)) + 0.15, mask="water", seed=R.randrange(9999))
                n += 1
                y += max(2, w * 0.35) * R.uniform(0.7, 1.4)
    print("window reflection dashes", n)

with doc.batch("ripples sky", author=A):
    n = 0
    for k in range(260):
        y = WL + 20 + (1080 - WL - 20) * (R.random() ** 1.6)
        t = (y - WL) / (1080 - WL)
        x = R.uniform(-50, 1920)
        ln = R.uniform(30, 160) * (0.5 + t)
        col = mix(SKY_MID, (0.55, 0.50, 0.65), R.random() * 0.5) if R.random() < 0.7 else (0.05, 0.06, 0.10)
        doc.stroke("water", curve((x, y), (x + ln, y + R.uniform(-1.5, 1.5)), n=8, pressure=(0.2, 1, 0.2)), col,
                   1.5 + 4 * t, brush="flat", opacity=0.35 + 0.3 * t, mask="water", seed=R.randrange(9999))
        n += 1
    print("sky ripples", n)
