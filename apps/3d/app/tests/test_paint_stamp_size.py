"""A stamp's Size on a clay (paint_mode.clay_stamp_reach): what would break silently is a stamp landing smaller or
larger than its Size where the clay's paint picture is denser or sparser (the core lays a clay's pieces at different
scales: the same Size in paint px gave a star 2-3× smaller on the side of a ball). It is screen px at the click, by the
view: the same click, the same metres, whatever the paint picture holds there."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screen3d import paint_mode as P  # noqa: E402

POSE = {"eye": [0, 0.14, 0.78], "target": [0, 0.1, 0], "fov": 27.0, "frame": 0, "width": 1300, "height": 760}


def test_a_clay_stamps_size_is_screen_px_at_the_click():
    d = 0.68
    per_px = d * 2 * math.tan(math.radians(27.0) / 2) / 760                  # metres one screen px spans there
    assert abs(P.clay_stamp_reach(55, d, POSE) - 55 / 2 * per_px) < 1e-6
    assert abs(P.clay_stamp_reach(55, 2 * d, POSE) - 2 * P.clay_stamp_reach(55, d, POSE)) < 2e-6   # twice as far
    assert P.clay_stamp_reach(55, None, POSE) == round(55 / 2 * P.GUESS_MPP, 6)    # no distance: the guess, loudly small
