# Jug, pass 4: break the light / shadow edge into painted dabs (warm pushed into the half-tone, cool
# pulled back into the light), and lay the table's warm bounce wider into the shadow side.
import random
from _geo import *

doc.add_layer("edges")
rnd = random.Random(41)
WARM = (0.98, 0.91, 0.77)
COOL = (0.83, 0.83, 0.89)
BOUNCE = (0.96, 0.70, 0.48)
seed = 700


def s():
    global seed
    seed += 1
    return seed


def at(y, t):
    l, r = edges(y)
    u = 2 * t - 1
    return l + (r - l) * t, y + sag(y) * (1 - u * u)


with doc.batch("broken light edge", author="agent:prop"):
    y = 110
    while y < 660:
        e = light_edge(y) + 0.12             # the edge sits a little right of the sun plane's end
        x0, y0 = at(y, e + rnd.uniform(-0.04, 0.02))
        length = rnd.uniform(18, 46)
        if rnd.random() < 0.65:              # warm dab pushed into the half-tone
            doc.stroke("edges", curve((x0 - 6, y0), (x0 + length, y0 + rnd.uniform(1, 5)), n=10, pressure=(1.0, 0.9, 0.2)),
                       WARM, rnd.randint(12, 20), brush="flat", mask="jug", opacity=0.85, color_jitter=0.05,
                       grain=0.45, size_pressure=0.6, seed=s())
        else:                                # cool dab pulled back into the light
            doc.stroke("edges", curve((x0 + 6, y0), (x0 - length, y0 + rnd.uniform(-2, 3)), n=10, pressure=(1.0, 0.9, 0.2)),
                       COOL, rnd.randint(10, 16), brush="flat", mask="jug", opacity=0.8, color_jitter=0.05,
                       grain=0.45, size_pressure=0.6, seed=s())
        y += rnd.uniform(9, 17)

with doc.batch("wide bounce", author="agent:prop"):
    for k in range(5):
        doc.stroke("edges", along_edge("right", 400 + k * 30, 690, 12 + k * 12, pressure=(0.05, 1.0, 0.7)),
                   BOUNCE, 26 - k * 3, brush="flat", mask="jug", opacity=0.55 - k * 0.07, color_jitter=0.06,
                   grain=0.45, size_pressure=0.6, seed=s())
print("edge strokes:", seed - 700)
