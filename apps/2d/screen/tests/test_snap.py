"""Snapping (screen2d/snap.py): a box a few screen px off the frame's centre lands on it; the distance is 6 screen px
at any zoom (so at 200 % it is 3 composition px); the frame comes before a nearer layer; Ctrl (no snap call) is free."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screen2d import snap as S  # noqa: E402

FRAME = S.frame_target(1920, 1080)


def box_at(cx, cy, w=200, h=100):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def test_centre_snaps_within_six_screen_px_at_any_zoom():
    dx, dy, lines = S.snap(box_at(964, 300), [FRAME], S.threshold(1.0))       # 4 screen px off at 100 %
    assert (dx, dy) == (-4, 0) and lines[0]["axis"] == "x" and lines[0]["at"] == 960
    dx, _, _ = S.snap(box_at(964, 300), [FRAME], S.threshold(2.0))           # 200 %: 4 comp px = 8 screen px: free
    assert dx == 0
    dx, _, _ = S.snap(box_at(962.5, 300), [FRAME], S.threshold(2.0))         # 2.5 comp px = 5 screen px: caught
    assert dx == -2.5


def test_frame_first_and_one_edge_for_a_resize():
    other = (1, (967, 0, 1100, 50))                                          # a layer edge nearer than the frame centre
    dx, _, _ = S.snap(box_at(964, 300), [FRAME, other], S.threshold(1.0))
    assert dx == -4
    dx, _, _ = S.snap((100, 100, 1917, 200), [FRAME], 6.0, xs=(2,), ys=())   # the right edge only
    assert dx == 3
