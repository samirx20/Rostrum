# Jug, pass 3: the marks that carry at frame size — a few big loaded strokes that turn with the belly,
# the worn rim edge, chips (iron showing through, a pale crack ring round each), the table bounce
# pushed further. Its own layer; the chips are listed for the misses check (misses.py).
import random
from _geo import *

doc.add_layer("accents")
rnd = random.Random(23)
HOT = (1.00, 0.95, 0.84)
WARM = (0.98, 0.90, 0.74)
COOL = (0.82, 0.83, 0.89)
BOUNCE = (0.95, 0.72, 0.52)
IRON = (0.20, 0.13, 0.09)
HALO = (0.97, 0.96, 0.92)
seed = 500
CHIPS = []


def s():
    global seed
    seed += 1
    return seed


with doc.batch("form strokes", author="agent:prop"):
    # long strokes that wrap the belly, loaded at the lit side, dragging thin into the half-tone
    for y in (230, 300, 372, 445, 520, 590):
        y += rnd.uniform(-12, 12)
        doc.stroke("accents", ring(y, 0.05, rnd.uniform(0.45, 0.58), n=14, pressure=(0.9, 1.0, 0.15)),
                   HOT if y < 450 else WARM, rnd.randint(20, 30), brush="flat", mask="jug", opacity=0.75,
                   color_jitter=0.05, grain=0.3, size_pressure=0.7, seed=s())
    for y in (260, 340, 420, 500):   # cool strokes pulled in from the shadow edge
        y += rnd.uniform(-12, 12)
        doc.stroke("accents", ring(y, rnd.uniform(0.55, 0.65), 0.97, n=12, pressure=(0.15, 1.0, 0.8)),
                   COOL, rnd.randint(18, 26), brush="flat", mask="jug", opacity=0.6, color_jitter=0.05,
                   grain=0.3, size_pressure=0.7, seed=s())

with doc.batch("bounce", author="agent:prop"):
    for k in range(4):
        doc.stroke("accents", along_edge("right", 420 + k * 25, 680, 8 + k * 7, pressure=(0.1, 1.0, 0.6)),
                   BOUNCE, 18 - k * 2, brush="flat", mask="jug", opacity=0.7, color_jitter=0.06, grain=0.4,
                   size_pressure=0.6, seed=s())

with doc.batch("worn rim edge", author="agent:prop"):
    # the lip's front edge, worn pale where the glaze is thin; strongest on the sun side
    doc.stroke("accents", ring(10, 0.04, 0.6, n=20, pressure=(0.8, 1.0, 0.2)), HALO, 4, brush="line", mask="jug",
               opacity=0.8, seed=s())

with doc.batch("chips", author="agent:prop"):
    # knocks happen on edges: the lip and the foot. Each chip = a pale broken ring (the white ground
    # cracked round it) and two or three small iron dabs, so it reads as a torn shape, not a dot.
    spots = [(424, 16, 5), (515, 24, 4), (606, 26, 6), (693, 20, 4), (731, 12, 3),    # lip
             (522, 704, 5), (688, 698, 4), (590, 709, 3),                               # foot
             (360, 150, 4)]                                                             # handle's top bar end
    for x, y, r in spots:
        doc.stroke("accents", curve((x - r, y + rnd.uniform(-1, 1)), (x + r, y + rnd.uniform(-1, 1)), n=6),
                   HALO, r * 1.8, brush="chalk", opacity=0.85, seed=s())
        ids = []
        for k in range(rnd.choice((2, 3))):
            dx, dy = rnd.uniform(-r * 0.6, r * 0.6), rnd.uniform(-r * 0.3, r * 0.3)
            ids.append(doc.stroke("accents", curve((x + dx - r * 0.3, y + dy), (x + dx + r * 0.3, y + dy + rnd.uniform(-1, 1)), n=5),
                                  IRON, r * rnd.uniform(0.6, 1.0), brush="round", hardness=0.85, seed=s()))
        CHIPS.extend(ids)
print("accent strokes:", seed - 500, "chip stroke ids:", " ".join(map(str, CHIPS)))
