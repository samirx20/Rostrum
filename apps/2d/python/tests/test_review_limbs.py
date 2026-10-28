"""What agents rely on when they take limb()'s defaults: a limb with no widths is sized to its body (not a thin fixed
width) and gets a hand shape; look_review's facts name an arm held nearly straight (and not a relaxed one), and limbs
thin next to the body (also in run_script's reply, through the document's advice)."""
from rostrum_core import Document

from rostrum2d import KIND, advice, run_source
from rostrum2d.mcp import review, review_limbs

SRC = '''
comp("c", width=960, height=540, duration=6, fps=10)
with rig("bot", w=960, h=540, x=480, y=270):
    hip = bone("hip", x=480, y=400, angle=-90, length=0)
    chest = bone("chest", parent=hip, length=120)
    body = shape("body", w=200, h=240, x=480, y=300, fill="#e8b64a")
    bind(layer=body, bone=chest)
    armL = limb("armL", parent=chest, x=380, y=220, lengths=(90, 80, 20){relax}{widths})
    pose({{armL: armL.out * 30}}, at=2.0)
'''


def _comp(relax="", widths=""):
    d = Document.new(KIND)
    d.run_script("bot.py", run_source(SRC.format(relax=relax, widths=widths), "bot.py"))
    return d, d.item("c")


def _straight(comp):
    times = [i * 0.5 for i in range(12)]
    return review_limbs.straight_arms(comp, times, 0.5)


def test_a_limb_with_no_widths_is_sized_to_its_body_and_has_a_hand():
    d, _ = _comp()
    arm, hand = d.item("armL"), d.item("armL_hand")
    assert 0.2 * 200 < arm["w"] <= 0.3 * 200                  # the upper part ~0.26 x the 200 px body, not a fixed 40
    assert hand["type"] == "path" and hand["w"] > 0.2 * 200     # a mitten, as wide as the arm


def test_straight_arms_are_named_and_a_relaxed_arm_is_not():
    _, comp = _comp(", relax=0")
    rows = _straight(comp)
    assert rows and rows[0]["kind"] == "arms_straight" and rows[0]["end"] - rows[0]["start"] >= 4
    assert "nearly straight" in rows[0]["text"] and '"armL"' in rows[0]["text"]
    _, comp = _comp()
    assert _straight(comp) == []


def test_thin_limbs_are_named_with_numbers_and_body_sized_ones_are_not():
    d, comp = _comp(widths=", widths=(24, 20, 30)")
    rows = review_limbs.thin_limbs(comp)
    assert [r["kind"] for r in rows] == ["limbs_thin"] and rows[0]["id"] == "bot"
    assert 'the arms are 24 px wide on a 200 px body' in rows[0]["text"] and "about 52 px" in rows[0]["text"]
    assert any("the arms are 24 px wide" in a for a in advice.advise(d.data))     # what run_script's reply carries
    d, comp = _comp()
    assert review_limbs.thin_limbs(comp) == [] and not any("px body" in a for a in advice.advise(d.data))


def test_a_cut_character_is_named_in_plain_words():
    row = review._cuts([{"type": "rig", "id": "app", "start": 23, "end": 30, "edge": "top", "cut_pct": 31}])[0]
    assert row["text"] == 'character "app" is cut by the top edge of the frame 23–30 s (31 % outside)'
