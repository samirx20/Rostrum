"""look_review names what the round-3 blind judges faulted: a near-empty frame mid-film, look-alike opening shots, an end
card held for a third of the film, a text crossed by a layer in front, a character hidden behind a desk or on a bare set;
and stays quiet on the same scenes made the other way."""
from rostrum_core import Document

from rostrum2d import KIND, run_source
from rostrum2d.mcp import review_cover, review_frame
from rostrum2d.mcp.review_sample import Sampled

STEP = 0.5
HEAD = 'comp("c", width=320, height=180, fps=10, duration={d}, background="#101010")\n'


def _sampled(src: str, d: float = 10) -> Sampled:
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(HEAD.format(d=d) + src, "s.py"))
    comp = doc.item("c")
    return Sampled(doc.data, comp, [round(i * STEP, 4) for i in range(int(d / STEP))], STEP)


def _kinds(rows):
    return {r["kind"]: r for r in rows}


def test_near_empty_mid_film():
    rows = review_frame.sparse(_sampled('shape("big", x=160, y=90, w=200, h=120, fill="#e0e0e0", start=0, end=4)\n'
                                        'shape("big2", x=160, y=90, w=200, h=120, fill="#e0e0e0", start=6, end=10)\n'
                                        'shape("dot", x=160, y=90, w=10, h=10, fill="#e0e0e0")'))
    assert [(r["start"], r["end"]) for r in rows] == [(4, 6)] and '"dot"' in rows[0]["text"] and "nearly empty" in rows[0]["text"]
    assert review_frame.sparse(_sampled('shape("big", x=160, y=90, w=200, h=120, fill="#e0e0e0")')) == []


def test_look_alike_opening_shots():
    jump = 'a.key("x", {0: 80, 2.99: 80, 3: 240, 5.99: 240, 6: 160})\n'
    rows = review_frame.opening(_sampled('a = shape("a", x=80, y=90, w=120, h=120, fill="#e0e0e0")\n' + jump, 12))
    assert rows and rows[0]["kind"] == "alike_open" and rows[0]["spans"] == [(0, 3), (3, 6), (6, 12)]
    assert "look alike" in rows[0]["text"] and '"a"' in rows[0]["text"]
    other = ('shape("a", x=80, y=90, w=120, h=120, fill="#e0e0e0", start=0, end=3)\n'
             'shape("b", x=240, y=60, w=60, h=40, fill="#ff0000", start=3, end=6)\n'
             'text("t", body="HELLO", size=40, x=160, y=90, start=6, end=12)\n')
    assert review_frame.opening(_sampled(other, 12)) == []


def test_end_card_held():
    moving = 'm = shape("m", x=40, y=90, w=60, h=60, fill="#e0e0e0", end=5)\nm.key("x", {0: 40, 5: 280})\n'
    rows = review_frame.end_hold(_sampled(moving + 'shape("logo", x=160, y=90, w=120, h=60, fill="#ffffff", start=5)'))
    assert len(rows) == 1 and rows[0]["start"] == 5 and "50 %" in rows[0]["text"] and '"logo"' in rows[0]["text"]
    drift = 'g = shape("logo", x=100, y=90, w=120, h=60, fill="#ffffff", start=5)\ng.key("x", {5: 100, 10: 250})'
    assert review_frame.end_hold(_sampled(moving + drift)) == []


def test_text_crossed_by_a_layer_in_front():
    title = 'text("title", body="Shaped", size=40, x=160, y=90)\n'
    pole = 'shape("pole", x=160, y=90, w=16, h=180, fill="#444444")\n'
    rows = review_cover.crossed(_sampled(title + pole))
    assert len(rows) == 1 and rows[0]["ids"] == ["title", "pole"] and (rows[0]["start"], rows[0]["end"]) == (0, 10)
    assert review_cover.crossed(_sampled(pole + title)) == []                                      # behind it
    assert review_cover.crossed(_sampled(title + pole.replace(")\n", ", opacity=0)\n"))) == []    # fully clear


RIG = '''
with rig("bot", w=320, h=180, x=160, y=90):
    hip = bone("hip", x=160, y=150, angle=-90, length=0)
    chest = bone("chest", parent=hip, length=60)
    body = shape("body", w=60, h=100, x=160, y=100, fill="#e8b64a")
    bind(layer=body, bone=chest)
'''
DESK = 'shape("desk", x=160, y=150, w=200, h=120, fill="#6b4a2a")\n'
SET = ''.join(f'shape("prop{i}", x={30 + i * 85}, y=40, w=60, h=60, fill="#3a6b8a")\n' for i in range(4))


def test_character_hidden_behind_a_desk_and_on_a_bare_set():
    rows = _kinds(review_cover.staging(_sampled(RIG + DESK)))
    assert rows["rig_hidden"]["id"] == "bot" and rows["rig_hidden"]["ids"][0] == "desk", rows
    assert rows["bare_set"]["id"] == "bot" and "bare set" in rows["bare_set"]["text"]
    rows = _kinds(review_cover.staging(_sampled(DESK + SET + RIG)))      # the desk behind it, a dressed set
    assert rows == {}, rows
