# Jug, pass 1: block in the enamel as painted shapes, through the shot camera.
# Sun comes from frame left (warm); room fill from the right (cool); the table bounces warm light
# up into the jug's shadow side. Strokes wrap the jug as rings; the shape edges are where stroke
# ends meet, staggered so the light / shadow edge is a broken, painted one.
import random
from _geo import *

doc.add_layer("enamel")
doc.mask_polygon("jug", JUG)
doc.mask_polygon("handle", HANDLE)
rnd = random.Random(7)

CREAM = (0.93, 0.90, 0.83)
WARM = (0.98, 0.92, 0.78)       # sun side
HOT = (1.00, 0.95, 0.84)        # the brightest plane, facing the sun
MID = (0.89, 0.87, 0.85)
COOL = (0.84, 0.84, 0.88)       # turned away, catching the cool room light
BOUNCE = (0.96, 0.72, 0.52)     # table light bounced into the shadow side
seed = 100


def s():
    global seed
    seed += 1
    return seed


with doc.batch("enamel ground", author="agent:prop"):
    doc.fill("enamel", CREAM, mask="jug")

with doc.batch("rings: sun, middle, cool", author="agent:prop"):
    y = 60
    while y < 700:
        a = light_edge(y) + rnd.uniform(-0.06, 0.06)     # sun plane ends
        b = a + 0.24 + rnd.uniform(-0.05, 0.05)          # half-tone ends, shadow plane starts
        for t0, t1, c, sz in [(0.0, a, WARM, rnd.randint(26, 40)), (a - 0.08, b, MID, rnd.randint(24, 36)),
                              (b - 0.05, 1.0, COOL, rnd.randint(28, 40))]:
            doc.stroke("enamel", ring(y + rnd.uniform(-5, 5), t0, min(t1, 1.0), n=16), c, sz, brush="flat",
                       mask="jug", opacity=0.85, color_jitter=0.07, grain=0.35, size_pressure=0.3, seed=s())
        y += rnd.randint(17, 25)

with doc.batch("sun plane", author="agent:prop"):
    # the brightest plane: where the shoulder and upper belly face the sun, broken at its edges
    for k in range(10):
        y0 = 130 + k * 42 + rnd.uniform(-8, 8)
        e = light_edge(y0)
        doc.stroke("enamel", ring(y0, 0.06 + rnd.uniform(-0.03, 0.03), e * 0.75 + rnd.uniform(-0.04, 0.04), n=10,
                                  pressure=(0.4, 1.0, 0.3)),
                   HOT, rnd.randint(30, 44), brush="flat", mask="jug", opacity=0.8, color_jitter=0.05,
                   grain=0.4, size_pressure=0.4, seed=s())

with doc.batch("table bounce", author="agent:prop"):
    for k in range(6):
        off = 10 + k * 9
        doc.stroke("enamel", along_edge("right", 360 + k * 18, 690, off, pressure=(0.2, 0.9, 0.5)),
                   BOUNCE, 22 - k * 2, brush="flat", mask="jug", opacity=0.55 - k * 0.06, color_jitter=0.06,
                   grain=0.4, size_pressure=0.5, seed=s())
    for k in range(5):   # the bounce also warms the underside of the belly, where it turns to the table
        doc.stroke("enamel", ring(560 + k * 22, 0.35 + 0.05 * k, 1.0, n=12, pressure=(0.2, 0.8, 0.8)),
                   BOUNCE, 24, brush="flat", mask="jug", opacity=0.35, color_jitter=0.06, grain=0.4, seed=s())

with doc.batch("handle ground", author="agent:prop"):
    doc.fill("enamel", CREAM, mask="handle")
    # outer edge faces the sun (left / up), inner edge turns away
    doc.stroke("enamel", curve(*[(x - 16, y + (12 if y < 200 else 0)) for x, y in HANDLE_PATH], n=60,
                               pressure=(0.9, 1, 0.9)),
               HOT, 24, brush="flat", mask="handle", opacity=0.9, color_jitter=0.05, grain=0.3, size_pressure=0.2,
               seed=s())
    doc.stroke("enamel", curve(*[(x + 16, y - (12 if y < 200 else 0)) for x, y in HANDLE_PATH], n=60,
                               pressure=(0.9, 1, 0.9)),
               COOL, 20, brush="flat", mask="handle", opacity=0.9, color_jitter=0.05, grain=0.3, size_pressure=0.2,
               seed=s())
print("enamel strokes:", seed - 100 + 2)
