"""What the live ink shows is what lands: the wet ink's pieces (wet_tip.Tip, as the screen lays them, a point a piece,
then the closing piece at the lift) are the saved stroke's pixels (the built item stamped whole, as the frame that
lands draws it), except over the stroke's last brush size or so, where its end frays and tapers. A smear included."""
import numpy as np
from rostrum_paint import canvas
from rostrum_paint.ops import build, seed_of

from screen2d.wet_ink import WetInk
from screen2d.wet_tip import Tip

SIZE = 120
BRUSH = {"brush": "bristle", "size": SIZE, "color": "#cc4033", "hardness": .6, "smudge": True, "wet": .35,
         "color_jitter": .08, "size_pressure": .5}
PTS = [[100 + 40 * i, 200 + 50 * np.sin(i / 4), 0.6] for i in range(16)]


def test_the_live_ink_is_the_saved_stroke_but_its_end():
    under = np.zeros((400, 900, 4), np.float32)
    under[:, ::60] = (0.1, 0.3, 0.5, 1.0)                                    # paint the smear drags
    ink = WetInk(BRUSH, "s1", 1.0, None, under)
    tip = Tip(ink._smeared())
    for k in range(1, len(PTS) + 1):
        tip.drawn(ink, PTS[:k])
    tip.drawn(ink, PTS, open_=False)
    saved = under.copy()
    canvas.stamp(saved, build("stroke", "s1", {**BRUSH, "seed": seed_of("s1"), "points": PTS}), 900, 400, {}, None)
    (ax, ay), (h, w) = tip.at, tip.px.shape[:2]
    x0, y0, x1, y1 = max(ax, 0), max(ay, 0), min(ax + w, 900), min(ay + h, 400)         # the canvas's part on the paint
    live, landed = tip.px[y0 - ay:y1 - ay, x0 - ax:x1 - ax], saved[y0:y1, x0:x1]
    end = int(PTS[-1][0] - 1.25 * SIZE) - x0
    assert np.abs(live[:, :end] - landed[:, :end]).max() < 1 / 255
    assert np.abs(live - landed).max() > 0.05            # (the end does differ: the check above is not empty)
