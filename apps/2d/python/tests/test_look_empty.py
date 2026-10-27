"""look_frame (what: empty): a blank mid-piece stretch, a blank ending and a long still stretch are named with times."""
import numpy as np

from rostrum2d.mcp.look_empty import analyse


def _frame(kind, i=0):
    img = np.full((90, 160, 3), 0.1, np.float32)
    if kind == "busy":
        img[10 + i % 40:40 + i % 40, 20:90] = 0.9          # something moving
    elif kind == "dot":
        img[40:42, 40:42] = 0.9
    return img


def test_blank_stretch_and_blank_ending_are_named_with_times():
    kinds = ["busy"] * 4 + ["blank"] * 4 + ["busy"] * 4 + ["dot"] * 2          # every 0.5 s: blank 2.0-4.0 s, near-empty ending 6.0-7.0 s
    rows = analyse([(i * 0.5, _frame(k, i)) for i, k in enumerate(kinds)], 0.5, 7.0)
    empty = [r for r in rows if r["kind"] == "empty"]
    assert [(r["start"], r["end"], r["ending"]) for r in empty] == [(2.0, 4.0, False), (6.0, 7.0, True)]
    assert "2–4 s: near-empty" in empty[0]["text"] and "the ending" in empty[1]["text"]
    assert not [r for r in rows if r["kind"] == "still"]      # blank stretches are not also reported as still


def test_unchanged_stretch_needs_min_still_seconds():
    imgs = [_frame("busy", 0)] + [_frame("busy", 5)] * 6                       # a held, non-empty picture
    rows = analyse([(i * 0.5, im) for i, im in enumerate(imgs)], 0.5, 3.5, min_still=2.0)
    assert [(r["kind"], r["start"], r["end"]) for r in rows] == [("still", 0.5, 3.5)] and rows[0]["ending"]
