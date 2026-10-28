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


def _phone(card_h, content):
    img = np.full((90, 160, 3), 0.93, np.float32)          # a pale page
    img[5:85, 60:100] = 0.1                                # the phone
    img[8:82, 62:98] = 0.97                                # its screen
    img[12:12 + card_h, 64:96] = (0.4, 0.3, 1.0)           # the card, growing
    if content:
        img[14:16, 66:90:3] = 1.0                          # its text, already on it
        img[12 + card_h // 2:12 + card_h // 2 + 2, 66:94:2] = 1.0
    return img


def test_a_card_growing_with_nothing_on_it_is_named_and_one_with_its_content_is_not():
    heights = [6, 6, 20, 40, 60, 60, 60]                   # every 0.5 s: it opens over 1.0-2.0 s, 6 % of the frame from 1.5 s
    bare = analyse([(i * 0.5, _phone(h, content=i >= 5)) for i, h in enumerate(heights)], 0.5, 3.5)
    block = [r for r in bare if r["kind"] == "block"]
    assert block and block[0]["start"] == 1.5 and "plain #" in block[0]["text"] and "nothing on it" in block[0]["text"]
    full = analyse([(i * 0.5, _phone(h, content=True)) for i, h in enumerate(heights)], 0.5, 3.5)
    assert not [r for r in full if r["kind"] == "block"]
