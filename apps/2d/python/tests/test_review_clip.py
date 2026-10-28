"""look_review names the two text faults a Gemini agent shipped in a laptop screen (Sam, 2026-10-28): code lines cut by
the screen's left edge, and a label covered by a panel group's own background drawn over it; a text sliding in through
the edge (a reveal) passes."""
from rostrum_core import Document

from rostrum2d import KIND, run_source
from rostrum2d.mcp import review_clip, review_layout
from rostrum2d.mcp.review_sample import Sampled

STEP = 0.5
HEAD = 'comp("c", width=320, height=180, fps=10, duration=6, background="#101010")\n'
SCREEN = 'with group("scr", x=160, y=90, w=200, h=120, clip=True):\n'


def _sampled(src: str) -> Sampled:
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(HEAD + src, "s.py"))
    return Sampled(doc.data, doc.item("c"), [round(i * STEP, 4) for i in range(12)], STEP)


def test_a_text_cut_by_its_screens_edge_is_named_with_the_side():
    rows = review_clip.facts(_sampled(SCREEN + '    text("code", body="reconcileClusterState()", size=14, x=10, y=30)\n'))
    assert [r["kind"] for r in rows] == ["text_clipped"] and rows[0]["ids"] == ["code", "scr"]
    assert "left edge" in rows[0]["text"]
    inside = SCREEN + '    text("code", body="ok()", size=14, x=100, y=30)\n'
    assert review_clip.facts(_sampled(inside)) == []


def test_a_text_sliding_in_through_the_edge_is_a_reveal():
    slide = SCREEN + '    text("code", body="reconcileClusterState()", size=14, x=10, y=30).key("x", {0: -100, 0.8: 100})\n'
    assert review_clip.facts(_sampled(slide)) == []


def test_a_panel_groups_background_drawn_over_a_label_crosses_it():
    src = ('text("value", body="TARGET ACQUIRED", size=24, x=160, y=80)\n'
           'with group("panel", x=160, y=110, w=240, h=40, background=True, bgColor="#131722"):\n'
           '    shape("bar", x=20, y=20, w=10, h=10, fill="#4f46e5")\n')
    rows = [r for r in review_layout.overlaps(_sampled(src)) if r["kind"] == "text_crossed"]
    assert rows and rows[0]["ids"] == ["value", "panel"]
