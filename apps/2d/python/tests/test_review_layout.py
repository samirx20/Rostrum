"""look_review names the layout faults Sam saw in a product film (a title partly under the card below it, a cursor on a
label, a tiny end card, a phone nibbled by a camera push-in) with ids and a fix, and stays quiet where the cover is meant
(a sheet fully over a screen, a frosted scrim, a deep push-in)."""
from rostrum_core import Document

from rostrum2d import KIND, run_source
from rostrum2d.mcp import review_device, review_layout
from rostrum2d.mcp.review_sample import Sampled

STEP = 0.5
HEAD = 'comp("c", width=320, height=180, fps=10, duration={d}, background="#101010")\n'


def _sampled(src: str, d: float = 6) -> Sampled:
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(HEAD.format(d=d) + src, "s.py"))
    return Sampled(doc.data, doc.item("c"), [round(i * STEP, 4) for i in range(int(d / STEP))], STEP)


def _kinds(rows):
    return {r["kind"]: r for r in rows}


SCREEN = '''
with group("home", x=160, y=90, w=200, h=160):
    with group("nav", x=100, y=20, w=200, h=40):
        text("nav_title", body="Trips", size=20, x=100, y={ty})
    with group("hero", x=100, y=80, w=180, h=80):
        shape("hero_bg", x=90, y=40, w=180, h=80, fill="#6a4dff")
'''


def test_text_partly_under_the_block_below_it_names_both_and_where_to_place_it():
    rows = _kinds(review_layout.overlaps(_sampled(SCREEN.format(ty=42))))
    assert rows["text_crossed"]["ids"] == ["nav_title", "hero_bg"]
    assert 'place "hero" below "nav"' in rows["text_crossed"]["text"] and "ends at y =" in rows["text_crossed"]["text"]
    assert "text_crossed" not in _kinds(review_layout.overlaps(_sampled(SCREEN.format(ty=20))))     # clear of it


def test_a_sheet_fully_over_a_text_or_a_frosted_scrim_is_not_a_crossing():
    title = 'text("title", body="Shaped", size=30, x=160, y=90)\n'
    sheet = 'shape("sheet", x=160, y=90, w=300, h=120, fill="#ffffff")\n'
    scrim = 'shape("scrim", x=160, y=60, w=300, h=60, fill="#ffffff").effect("backdrop", radius=20)\n'
    assert review_layout.overlaps(_sampled(title + sheet)) == []
    assert review_layout.overlaps(_sampled(title + scrim)) == []


def test_texts_on_texts_but_not_a_short_cross_fade_swap():
    a = 'text("a", body="Total", size=24, x=160, y=80)\n'
    rows = review_layout.overlaps(_sampled(a + 'text("b", body="$46.60", size=24, x=170, y=92)\n'))
    assert [r["kind"] for r in rows] == ["text_on_text"] and rows[0]["ids"] == ["a", "b"]
    swap = ('text("a", body="Send", size=24, x=160, y=90, end=3.4)\n'
            'text("b", body="Sent", size=24, x=160, y=90, start=2.6)\n')
    assert review_layout.overlaps(_sampled(swap)) == []


def test_a_cursor_on_a_label():
    label = 'text("send_lbl", body="Send requests", size=20, x=160, y=90)\n'
    rows = _kinds(review_layout.overlaps(_sampled(label + 'shape("cursor", shape="ellipse", x=150, y=90, w=30, h=30, fill="#222")\n')))
    assert rows["pointer_on_text"]["ids"] == ["send_lbl", "cursor"] and 'spot="beside"' in rows["pointer_on_text"]["text"]
    away = review_layout.overlaps(_sampled(label + 'shape("cursor", shape="ellipse", x=40, y=30, w=30, h=30, fill="#222")\n'))
    assert away == []
    assert review_layout.overlaps(_sampled(label + 'shape("handle", x=150, y=90, w=30, h=30, fill="#222")\n'))[0]["kind"] == "text_crossed"


def test_a_tiny_end_card_but_not_a_normal_lock_up():
    tiny = review_layout.end_card(_sampled('shape("mark", x=150, y=90, w=10, h=10, fill="#6a4dff")\n'
                                           'text("word", body="Tally", size=8, x=172, y=90)\n'))
    assert tiny and tiny[0]["kind"] == "end_small" and "scale the lock-up up" in tiny[0]["text"]
    normal = review_layout.end_card(_sampled('shape("mark", x=160, y=64, w=56, h=56, fill="#6a4dff")\n'
                                             'text("word", body="Tally", size=30, x=160, y=126)\n'))
    assert normal == []


PHONE = '''
with group("phone", x=160, y=90, w=60, h=120):
    shape("phone_body", x=30, y=60, w=60, h=120, fill="#222")
    with group("phone_screen", x=30, y=60, w=54, h=112, clip=True):
        text("t", body="Lisbon", size=10, x=27, y=10)
'''


def test_a_phone_placed_off_the_frame_or_nibbled_by_a_push_in_but_not_a_deep_push_in():
    assert _kinds(review_device.facts(_sampled(PHONE.replace('y=90, w=60', 'y=40, w=60'))))["device_cut"]["id"] == "phone"
    push = _kinds(review_device.facts(_sampled(PHONE + 'frame().fit(rect=(85, 48, 150, 84), at=0)\n')))
    assert 'frame().fit(["phone"]' in push["push_cut"]["text"] and "% of the film" in push["push_cut"]["text"]
    deep = review_device.facts(_sampled(PHONE + 'frame().fit(rect=(140, 60, 40, 22), at=0)\n'))
    assert [r["kind"] for r in deep] == ["push_in"] and deep[0]["info"]


def test_a_word_a_deep_push_in_slices_at_the_frame_edge_is_named_not_kept_as_info():
    from rostrum2d.mcp import review
    src = HEAD.format(d=6) + PHONE + '        text("s", body="Summarise", size=10, x=27, y=52)\nframe().fit(rect=(140, 60, 40, 22), at=0)\n'
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    faults, _ = review.doc_faults(doc.data, doc.item("c"), None, "look_review")
    cut = [f for f in faults if f["kind"] in ("text_edge", "small_text_edge") and "s" in (f.get("ids") or [f["id"]])]
    assert cut and not any(f.get("info") for f in cut)
