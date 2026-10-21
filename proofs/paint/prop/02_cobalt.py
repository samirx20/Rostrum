# Jug, pass 2: the cobalt glaze — rim band with a hand-painted scalloped edge, the foot band, and the
# stripe down the handle. Its own layer so it can be judged and undone apart from the enamel.
import random
from _geo import *

doc.add_layer("cobalt")
rnd = random.Random(11)
DEEP = (0.10, 0.16, 0.52)
LIT = (0.20, 0.32, 0.72)      # cobalt where the sun hits it
seed = 300


def s():
    global seed
    seed += 1
    return seed


with doc.batch("rim band", author="agent:prop"):
    y = 0
    while y < 62:
        doc.stroke("cobalt", ring(y, 0.0, 0.45, n=14), LIT, rnd.randint(16, 22), brush="flat", mask="jug",
                   color_jitter=0.08, grain=0.3, size_pressure=0.2, seed=s())
        doc.stroke("cobalt", ring(y + 2, 0.38, 1.0, n=14), DEEP, rnd.randint(16, 22), brush="flat", mask="jug",
                   color_jitter=0.08, grain=0.3, size_pressure=0.2, seed=s())
        y += 12
    # the dipped edge: short loaded strokes pulled down out of the band, uneven lengths, tapering out
    l, r = edges(60)
    x = l + 6
    while x < r - 6:
        t = (x - l) / (r - l)
        yb = 58 + sag(58) * (1 - (2 * t - 1) ** 2)
        c = LIT if t < 0.40 + rnd.uniform(-0.05, 0.05) else DEEP
        drop = rnd.choice((rnd.uniform(4, 12), rnd.uniform(10, 30)))
        doc.stroke("cobalt", curve((x, yb - 6), (x + rnd.uniform(-2, 2), yb + drop), n=12, pressure=(1.0, 0.8, 0.2)),
                   c, rnd.randint(11, 17), brush="flat", mask="jug", color_jitter=0.06, size_pressure=0.9,
                   grain=0.2, seed=s())
        x += rnd.uniform(7, 26)

with doc.batch("foot band", author="agent:prop"):
    for y in (640, 650, 661, 672):
        doc.stroke("cobalt", ring(y + rnd.uniform(-2, 2), 0.0, 0.45, n=14), LIT, 16, brush="flat", mask="jug",
                   color_jitter=0.08, grain=0.3, size_pressure=0.2, seed=s())
        doc.stroke("cobalt", ring(y + rnd.uniform(-2, 2), 0.38, 1.0, n=14), DEEP, 16, brush="flat", mask="jug",
                   color_jitter=0.08, grain=0.3, size_pressure=0.2, seed=s())

with doc.batch("handle stripe", author="agent:prop"):
    doc.stroke("cobalt", curve(*HANDLE_STRIPE, n=80, pressure=(0.8, 1, 0.8)), DEEP, 7, brush="round",
               hardness=0.8, mask="handle", color_jitter=0.06, size_pressure=0.4, seed=s())
print("cobalt strokes:", seed - 300)
