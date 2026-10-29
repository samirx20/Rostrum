"""The look names, before export, what Sam saw at once in two agent films: cards placed by hand running into each
other (with the y that fixes it, in the px the script types), a subject never on screen, a tap's pointer resting on a
long label's letters, a heading crossed by a ring drawn behind it, and words with no padding on their card."""
from rostrum_core import Document

from rostrum2d import KIND, run_source
from rostrum2d.mcp import review_layout, review_offscreen, review_padding, review_panels
from rostrum2d.mcp.review_sample import Sampled

STEP = 0.5
HEAD = 'comp("c", width=640, height=360, fps=10, duration=4, background="#101010")\n'


def _sampled(src: str) -> Sampled:
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(HEAD + src, "s.py"))
    return Sampled(doc.data, doc.item("c"), [round(i * STEP, 4) for i in range(8)], STEP)


CARDS = '''
frame(zoom=1.5)
with group("pane", x=320, y=180, w=600, h=340):
    with group("a", x=50, y=40, w=300, h=40, anchorX=0, anchorY=0, background=True, bgColor="#223"):
        text("a_t", body="First card", size=14, x=150, y=60)
    with group("b", x=50, y=90, w=300, h=40, anchorX=0, anchorY=0, background=True, bgColor="#223"):
        text("b_t", body="Second card", size=14, x=150, y=20)
'''


def test_cards_running_into_each_other_are_named_with_the_y_to_type():
    rows = [f for f in review_panels.facts(_sampled(CARDS)) if f["kind"] == "panel_overlap"]
    assert len(rows) == 1 and rows[0]["ids"] == ["a", "b"]
    # a's words reach y = 40 + 60 + half a line (its drawn extent, not h=40); b moves to that + 16, in pane px, not the
    # zoomed picture's px
    assert '"pane" px' in rows[0]["text"] and 'set "b" y = ' in rows[0]["text"]
    y = float(rows[0]["text"].split('set "b" y = ')[1].split(",")[0])
    assert 120 < y < 140


def test_a_group_never_in_the_picture_is_named_once_and_one_partly_in_is_not():
    src = '''
with group("arm", x=-900, y=180):
    shape("base", w=120, h=60, fill="#888")
    shape("link", y=-80, w=30, h=140, fill="#888")
with group("cart", x=620, y=180):
    shape("body", w=120, h=60, fill="#888")
'''
    rows = review_offscreen.facts(_sampled(src))
    assert [r["id"] for r in rows] == ["arm"] and "never on screen" in rows[0]["text"]


def test_a_pointer_on_a_long_labels_letters_is_named_whatever_its_id():
    src = '''
text("label", body="DEPLOY AUTONOMOUS SYNTHESIS NOW", size=24, x=320, y=180)
cur = pointer("st7_cur", x=300, y=176)
'''
    rows = [f for f in review_layout.overlaps(_sampled(src)) if f["kind"] == "pointer_on_text"]
    assert rows and rows[0]["ids"] == ["label", "st7_cur"]


def test_a_ring_drawn_behind_a_heading_crosses_it():
    src = '''
shape("ring", shape="ellipse", x=320, y=200, w=300, h=300, filled=False, stroke=True, strokeColor="#38bdf8", strokeWidth=4)
text("head", body="ANY-TO-ANY NATIVE", size=30, x=320, y=60)
'''
    rows = [f for f in review_layout.overlaps(_sampled(src)) if f["kind"] == "text_crossed"]
    assert rows and rows[0]["ids"] == ["head", "ring"]


def test_words_touching_their_cards_side_are_named_and_padded_ones_are_not():
    src = '''
shape("card", x=320, y=180, w={w}, h=120, fill="#334")
text("words", body="VOICE VISION CODE", size=40, x=320, y=180)
'''
    tight = review_padding.facts(_sampled(src.format(w=200)))
    assert tight and tight[0]["ids"] == ["words", "card"] and "no padding" in tight[0]["text"]
    assert not review_padding.facts(_sampled(src.format(w=600)))
