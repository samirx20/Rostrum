"""Night Market (rebench 3E): a hand-lettered title on a canvas-sized drawing pushed past the top edge, and lit windows
painted on a later paint layer over the awnings. Both went out unnamed; both must be named now."""
from rostrum2d.mcp import review_facts, review_paint_order, review_room
from rostrum2d.mcp.review_sample import Sampled
from rostrum2d.script import run_source

SRC = '''
comp("main", width=1920, height=1080, fps=30, duration=4, background="#0b1230")
d = drawing("wash", w=1920, h=1080)
f = d.frame(0)
walls = f.paint("walls")
walls.fill([(100, 300), (700, 300), (700, 800), (100, 800)], color="#334488")
walls.fill([(150, 560), (650, 560), (650, 640), (150, 640)], color="#cc4433")    # an awning in front of the wall
lit = f.paint("lights")
lit.fill([(300, 520), (340, 520), (340, 600), (300, 600)], color="#ffb347")      # half on the awning, painted after it
lit.fill([(450, 350), (490, 350), (490, 400), (450, 400)], color="#ffb347")      # wholly in the wall: fine
t = drawing("title", w=1920, h=1080)
t.frame(0).paint("ink").letters("Night Market", x=960, y={y}, height=125, font="script", align="center", size=16)
'''


def test_lettered_title_past_the_top_is_cut():
    comp = run_source(SRC.replace("{y}", "60"), "t.py")["comps"][0]
    times = [i * 0.5 for i in range(8)]
    rows = review_facts.layer_facts(comp, times, 0.5) + review_room.facts(comp, times, 0.5)
    assert ("text_edge", "title") in {(r["kind"], r["id"]) for r in rows}
    clear = run_source(SRC.replace("{y}", "400"), "t.py")["comps"][0]
    rows = review_facts.layer_facts(clear, times, 0.5) + review_room.facts(clear, times, 0.5)
    assert not [r for r in rows if r.get("id") == "title"]


def test_patch_painted_after_over_a_shape_is_named():
    doc = run_source(SRC.replace("{y}", "400"), "t.py")
    comp = doc["comps"][0]
    rows = review_paint_order.facts(Sampled(doc, comp, [0.0, 0.5], 0.5))
    assert [r["kind"] for r in rows] == ["painted_over"]
    assert rows[0]["ids"][1:] == ["fill_3", "fill_2"]
