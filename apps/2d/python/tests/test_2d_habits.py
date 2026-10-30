"""Agents' common habits from CSS, SVG and LaTeX are read, not refused, and the reply says how: a CSS margin list,
dash=[8, 8], ease on frame().home(), LaTeX's sized brackets (\\Big( …)."""
import pytest
from rostrum_core import Document

from rostrum2d import KIND, layout, pathdata, run_source, textsize
from rostrum2d.mathtype import math_parts
from fake_layout import FakeEngine

HEAD = 'comp("main", width=1920, height=1080, fps=30, duration=6)\n'


def layers(tree):
    out = {}

    def walk(n):
        for c in n.get("layers", []):
            out[c["id"]] = c
            walk(c)
    walk(tree["comps"][0])
    return out


def test_a_css_margin_list_is_read_top_right_bottom_left_and_sent_as_one():
    src = HEAD + '''with column("col", gap=0):
    shape("a", w=100, h=50, margin=[38, 0, 0, 0])
    shape("b", w=100, h=50, margin=[10, 20])
    shape("c", w=100, h=50, margin=[6])
'''
    tree = run_source(src, "s.py")
    d = layers(tree)
    a, b, c = d["a"], d["b"], d["c"]
    assert (a["margin"], a["marginTop"], a["marginRight"], a["marginBottom"], a["marginLeft"]) == (0, 38, 0, 0, 0)
    assert (b["margin"], b["marginTop"], b["marginRight"], b["marginBottom"], b["marginLeft"]) == (10, 0, 10, 0, 10)
    assert (c["margin"], c["marginTop"]) == (6, 0)
    assert 'shape("a"): margin=[38, 0, 0, 0] was read as CSS (top, right, bottom, left): top 38, right 0, bottom 0, left 0' in tree.notes
    assert not any('shape("c")' in n for n in tree.notes)          # one number for every side: nothing to say
    doc = Document.new(KIND)
    with textsize.use(FakeEngine()):
        doc.run_script("s.py", tree)
        kids = {k["id"]: k for k in layout.Plan(doc.item("main"), 0.0).trees[0]["children"]}
    assert kids["a"]["style"]["margin"] == [38, 0, 0, 0] and kids["b"]["style"]["margin"] == [10, 20, 10, 20]
    assert kids["c"]["style"]["margin"] == 6


@pytest.mark.parametrize("bad", ["[1, 2, 3, 4, 5]", "['a']"])
def test_a_margin_list_that_is_not_css_is_refused(bad):
    with pytest.raises(Exception) as e:
        run_source(HEAD + f'with column("col"):\n    shape("a", w=10, h=10, margin={bad})\n', "s.py")
    assert "top, right, bottom, left" in str(e.value)


def test_dash_as_an_svg_list_is_dash_and_gap():
    tree = run_source(HEAD + 'path("sq", d="M0 0 L100 0", stroke=True, dash=[8, 4])\npath("ci", d="M0 0 L50 0", stroke=True, dash=[6])\n', "s.py")
    d = layers(tree)
    assert (d["sq"]["dash"], d["sq"]["gap"]) == (8, 4) and (d["ci"]["dash"], d["ci"]["gap"]) == (6, 6)
    assert "sq.dash: dash=[8, 4] was read as SVG / CSS dashes: dash 8, gap 4" in tree.notes
    with pytest.raises(Exception) as e:
        run_source(HEAD + 'path("sq", d="M0 0 L10 0", stroke=True, dash=[8, 4, 2, 4])\n', "s.py")
    assert "one dash and one gap" in str(e.value)


def test_frame_home_takes_an_ease_for_the_move_home():
    src = HEAD + 'shape("box", x=3000, y=500, w=400, h=300)\nf = frame()\nf.fit(["box"], at=2)\nf.home(at=5, ease="easeInOut")\n'
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    zs = sorted((k["t"], k["v"], k["ease"]) for k in doc.item("frame")["keys"] if k["prop"] == "zoom")
    assert [t for t, _, _ in zs] == [0.0, 2, 5] and zs[-1][1] == 1.0
    assert zs[1][2] == "easeInOut"                                    # the key before home shapes the move home
    xs = sorted((k["t"], k["ease"]) for k in doc.item("frame")["keys"] if k["prop"] == "x")
    assert xs[1][1] == "custom"                                       # the centre follows the zoom, as fit's move


def _heights(tex):
    return [(w, round(pathdata.bounds(pathdata.commands(d))[3] - pathdata.bounds(pathdata.commands(d))[1], 1))
            for w, d in math_parts(tex, 64)]


def test_latex_sized_brackets_are_drawn_taller_in_order():
    plain = dict(_heights(r"(x)"))["lparen"]
    sizes = [dict(_heights(rf"\{s}( x \{s})"))["lparen"] for s in ("big", "Big", "bigg", "Bigg")]
    assert plain < sizes[0] < sizes[1] < sizes[2] < sizes[3]
    assert 1.6 < sizes[1] / plain < 2.0                               # \Big: about 1.8 times, as LaTeX
    assert [w for w, _ in _heights(r"\Bigl[ x \Bigr]")] == ["lbracket", "x", "rbracket"]
    assert [w for w, _ in _heights(r"\left\{ x \right\}")] == ["lbrace", "x", "rbrace"]
    tree = run_source(HEAD + 'math_text("eq", r"\\Big( \\frac{a}{b} \\Big)")\n', "s.py")
    assert 'math_text "eq": LaTeX\'s sized brackets (\\big, \\Big, \\bigg, \\Bigg) were drawn at about LaTeX\'s heights' in tree.notes
