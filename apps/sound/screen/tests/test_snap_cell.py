"""A click that makes something lands in the grid cell under the pointer, never a step late (critic r5 M1): the screen
paints a line on its nearest whole pixel, so a press on that pixel is on the line, one pixel before it is the cell
before, and anything after it up to the next line is that line's cell."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screensound import timing  # noqa: E402

ROOT = {"tempo": 100.0, "beatsPerBar": 4}         # a beat is 0.6 s
SPB = 0.6


def grid(value):
    g = timing.Grid()
    g.value = value
    return g


def test_a_click_takes_the_cell_under_the_pointer():
    for value, step, px_per_beat in (("1/16", 0.25, 12.15), ("beat", 1.0, 12.15), ("1/16", 0.25, 40.0)):
        px = SPB / px_per_beat                                   # one screen pixel, in seconds
        g = grid(value)
        line = 48 * SPB                                          # bar 13
        drawn = round(line / px) * px                            # where the screen paints it
        for dx in (0, 1, 2):                                     # on the line's pixel, or just after it
            if dx * px < step * SPB:
                assert timing.snap(drawn + dx * px, ROOT, False, g, "cell", px) == round(line, 6), (value, dx)
        before = timing.snap(drawn - px, ROOT, False, g, "cell", px)
        assert abs(before - (line - step * SPB)) < 1e-6, value   # a pixel before the line: the cell before

