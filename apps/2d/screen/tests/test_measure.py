"""Alt measuring (screen2d/measure.py): the numbers are the true px gaps between the picked layer's box and the hovered
one, or its distances to the frame's edges; nothing is drawn for a zero distance."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screen2d import measure as M  # noqa: E402


def _gaps(lines):
    return sorted((l["along"], l["gap"]) for l in lines if not l.get("guide"))


def test_inside_the_frame_four_distances_to_its_edges():
    assert _gaps(M.lines((100, 50, 300, 150), (0, 0, 1920, 1080))) == [("x", "100"), ("x", "1620"), ("y", "50"), ("y", "930")]


def test_side_by_side_one_gap_at_the_middle_of_their_overlap():
    lines = M.lines((0, 0, 100, 100), (148, 40, 200, 200))
    assert _gaps(lines) == [("x", "48")] and lines[0]["at"] == 70 and (lines[0]["from"], lines[0]["to"]) == (100, 148)


def test_apart_both_ways_two_gaps_and_guides_to_the_other_box():
    lines = M.lines((0, 0, 100, 100), (130, 160, 200, 200))
    assert _gaps(lines) == [("x", "30"), ("y", "60")] and sum(1 for l in lines if l.get("guide")) == 2


def test_touching_edges_and_shared_edges_draw_nothing():
    assert M.lines((0, 0, 100, 100), (100, 0, 200, 100)) == []
    assert _gaps(M.lines((0, 0, 100, 100), (0, 0, 100, 40.5))) == [("y", "59.5")]
