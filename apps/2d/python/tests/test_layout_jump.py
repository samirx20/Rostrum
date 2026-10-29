"""A row keeps its place and its slots while its cards fade in one by one (layout.py: opacity and shifts never free a
slot; a layer outside its start..end takes no room, as the script wrote it), and review names a layer its layout jumps in one frame (review_jump), not a smooth re-flow.
Canary 3E R8: a row of pricing cards fading in looked as if it re-centred."""
from rostrum_core import Document

from rostrum2d import KIND, layout, run_source, textsize
from rostrum2d.mcp import review_jump
from rostrum2d.mcp.review_sample import Sampled
from fake_layout import FakeEngine

HEAD = 'comp("c", width=1000, height=600, fps=10, duration=3)\n'
CARDS = '''
with row("cards", x=100, y=300, w=800, gap=20, justify="center"):
    for i in range(3):
        shape(f"card_{i}", w=200, h=120)
for i in range(3):
    layer(f"card_{i}").key("opacity", {i * 0.8: 0, i * 0.8 + 0.4: 1}).key("shiftY", {i * 0.8: 40, i * 0.8 + 0.4: 0})
'''


def _doc(src):
    d = Document.new(KIND)
    d.run_script("s.py", run_source(HEAD + src, "s.py"))
    return d


def test_cards_fading_in_one_by_one_keep_the_row_and_their_slots():
    with textsize.use(FakeEngine()):
        comp = _doc(CARDS).item("c")
        seen = [layout.solve(comp, t) for t in (0.0, 0.3, 0.9, 1.7, 2.5)]
    for i in range(3):
        xs = {s[f"card_{i}"]["x"] for s in seen}
        ys = {round(s[f"card_{i}"]["y"] - layout.resolve(comp["layers"][1]["layers"][i], t)["shiftY"], 3)
              for s, t in zip(seen, (0.0, 0.3, 0.9, 1.7, 2.5))}
        assert len(xs) == 1 and len(ys) == 1, f"card_{i} moved: {xs} {ys}"
    assert len({tuple(sorted(s.get("cards", {}).items())) for s in seen}) == 1


def test_a_card_before_its_start_takes_no_room():
    with textsize.use(FakeEngine()):
        comp = _doc(CARDS.replace("h=120)", "h=120, start=i * 0.8)")).item("c")
        early, late = layout.solve(comp, 0.0), layout.solve(comp, 2.5)
    assert "card_2" not in early and "card_2" in late


def _jumps(src):
    with textsize.use(FakeEngine()):
        d = _doc(src)
        times = [i * 0.5 for i in range(6)]
        return review_jump.facts(Sampled(d.data, d.item("c"), times, 0.5))


ROW = '''
with row("r", x=100, y=300, anchorX=0, gap=10):
    shape("a", w=50, h=50)
    shape("b", w=50, h=50)
    shape("c2", w=50, h=50)
layer("b").key("w", {{1.0: 50, {to}: 400}}{ease})
'''


def test_a_layout_jump_is_named_and_a_smooth_reflow_or_cards_coming_in_are_not():
    rows = _jumps(ROW.format(to=1.1, ease=', ease="hold"'))
    assert [r["id"] for r in rows] == ["c2"] and rows[0]["kind"] == "layout_jump" and rows[0]["end"] - rows[0]["start"] < 0.11
    assert _jumps(ROW.format(to=3.0, ease="")) == []
    assert _jumps(CARDS) == []
