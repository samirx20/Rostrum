"""Align moves a point text's anchor with it, for a script and an operation alike, and keeps an anchor someone placed
(text_anchor.py): what makes Paragraph › Align › Center centre a title on its x. No engine needed."""
from rostrum_core import Document, Who
from rostrum2d import KIND, run_source

SAM = Who.person("sam")
SRC = '''
comp("c", width=1920, height=1080)
text("col", body="A", align="left")
text("own", body="B", align="left", anchorX=0.3)
text("box", body="C", boxWidth=400)
'''


def _doc(tmp_path):
    d = Document.new(KIND, folder=str(tmp_path), item="p")
    d.run_script("a.py", run_source(SRC, "a.py"))
    return d


def test_align_moves_the_anchor_unless_someone_placed_it(tmp_path):
    d = _doc(tmp_path)
    assert d.item("col")["anchorX"] == 0.0 and d.item("own")["anchorX"] == 0.3    # a script: left = x is the left edge
    for align, ax in (("center", 0.5), ("right", 1.0), ("left", 0.0)):
        d.apply({"op": "text.set", "target": ["col", "own", "box"], "args": {"align": align}}, SAM)
        assert d.item("col")["anchorX"] == ax
        assert d.item("own")["anchorX"] == 0.3 and d.item("box")["anchorX"] == 0.5   # placed by hand; a box stays put
    d.undo(SAM)                                                          # the anchor comes back with the alignment
    col = d.item("col")
    assert col["align"] != "left" and col["anchorX"] == {"center": 0.5, "right": 1.0}[col["align"]], col
