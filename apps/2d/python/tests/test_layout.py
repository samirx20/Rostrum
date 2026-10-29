"""Auto layout asks the engine's CSS layout (layout.py): the trees it sends must say what the document says (styles,
set-apart layers as absolute boxes, hidden layers absent), and the boxes that come back must become the layers' x / y
(by anchor, plus shift), and a narrowed text's boxWidth, or every laid-out film draws in the wrong place silently.
A fake engine stands in (the real `layout` request is the engine's; tests/fake_layout.py)."""
from rostrum_core import Document

from rostrum2d import KIND, layout, layoutbake, migrations, run_source, textsize
from fake_layout import FakeEngine


def _comp(src):
    d = Document.new(KIND)
    with textsize.use(FakeEngine()):
        d.run_script("a.py", run_source('comp("c", width=1000, height=600, fps=10, duration=1)\n' + src, "a.py"))
    return d.item("c")


SRC = '''
with group("g", x=0, y=0, w=400, anchorX=0, anchorY=0, layout="column", gap=8, padding=12, paddingX=20,
           justify="between", align="center", clip=True, sizeW="fixed", sizeH="fit"):
    shape("a", w=100, h=50, layoutGrow=2, alignSelf="end", margin=4, shiftX=5, shiftY=-3)
    text("t", body="Twenty characters!!!", size=20)
    shape("free", x=7, y=9, w=10, h=10, anchorX=0, anchorY=0, layoutApart=True)
    shape("gone", w=10, h=10, hidden=True)
    with group("inner", layout="row", gap=4, sizeW="fill"):
        shape("b", w=30, h=30, sizeW="percent", pctW=50)
'''


def test_tree_says_what_the_document_says():
    plan = layout.Plan(_comp(SRC), 0.0)
    assert len(plan.trees) == 1                                             # the inner box is part of the one tree
    root = plan.trees[0]
    s = root["style"]
    assert s["display"] == "flex" and s["direction"] == "column" and s["rowGap"] == 8
    assert s["padding"] == [12, 20, 12, 20] and s["justify"] == "between" and s["align"] == "center"
    assert s["overflow"] == "hidden" and s["width"] == 400 and s["height"] == "fit"
    kids = {k["id"]: k for k in root["children"]}
    assert "gone" not in kids                                               # hidden: takes no room
    a = kids["a"]
    assert a["kind"] == "leaf" and (a["w"], a["h"]) == (100, 50)
    assert a["style"] == {"alignSelf": "end", "margin": 4, "grow": 2, "shrink": 0.0}
    t = kids["t"]
    assert t["kind"] == "text" and t["text"]["body"] == "Twenty characters!!!" and "boxWidth" not in t["text"]
    assert t["style"]["shrink"] == 1.0
    assert kids["free"]["style"] == {"position": "absolute", "left": 7, "top": 9}
    inner = kids["inner"]
    assert inner["kind"] == "box" and inner["style"]["alignSelf"] == "stretch" and inner["style"]["width"] == "auto"
    assert inner["style"]["columnGap"] == 4 and inner["children"][0]["style"]["width"] == "50%"


def test_stack_and_grid_cells():
    comp = _comp('''
with group("s", layout="stack", justify="center", align="end"):
    shape("a", w=10, h=10)
with group("g", layout="grid", columns=3, align="center"):
    shape("b", w=10, h=10, colSpan=2)
''')
    s, g = layout.Plan(comp, 0.0).trees
    assert s["style"]["display"] == "stack" and s["style"]["justify"] == "center" and s["style"]["align"] == "end"
    assert g["children"][0]["style"]["justifySelf"] == "center"
    assert g["style"]["columns"] == 3 and g["children"][0]["style"]["colSpan"] == 2


def test_boxes_become_places_by_anchor_and_shift_and_a_narrowed_text_wraps_there():
    comp = _comp(SRC)
    eng = FakeEngine(boxes={"g": [0, 0, 400, 260], "a": [10, 20, 100, 50], "t": [20, 80, 120, 60],
                            "free": [7, 9, 10, 10], "inner": [20, 150, 360, 30], "b": [0, 0, 180, 30]})
    with textsize.use(eng):
        out = layout.solve(comp, 0.0)
    a = out["a"]
    assert (a["x"], a["y"]) == (10 + 0.5 * 100 + 5, 20 + 0.5 * 50 - 3)       # slot + anchor × size + shift
    t = out["t"]
    assert t["boxWidth"] == 120 and t["x"] == 20                 # one line is 200 px: it wraps at 120; a text in a box reads from the left
    assert t["y"] == 80 + 0.5 * 40                                           # its two lines, at the top of a taller slot
    assert "free" not in out                                                 # set apart: keeps its own x, y
    assert out["g"]["h"] == 260 and out["g"]["w"] == 400                     # fits its content: the height follows
    assert out["b"]["w"] == 180 and "boxWidth" not in out["a"]


def test_a_layout_that_doesnt_move_is_one_engine_call_and_frames_go_together():
    comp = _comp('with group("g", layout="row"):\n    shape("a", w=10, h=10)\n')
    eng = FakeEngine()
    layout._answers.clear()
    with textsize.use(eng):
        layout.solve(comp, 0.0)
        layout.solve(comp, 0.5)
        layoutbake.bake(comp, 10)
    assert len(eng.layouts) == 1
    moving = _comp('with group("g", layout="row"):\n    shape("a", h=10, w=10).key("w", {0: 10, 1: 100})\n')
    eng = FakeEngine()
    layout._answers.clear()
    with textsize.use(eng):
        keys = layoutbake.bake(moving, 10)
    assert len(eng.layouts) == 1 and len(eng.layouts[0]) == 11              # 11 frames' trees, one request
    assert keys["g"]["w"][-1]["v"] == 120


def test_old_hug_switches_become_size_modes():
    data = {"id": "root", "type": "doc", "comps": [{"id": "c", "type": "comp", "layers": [
        {"type": "group", "id": "g", "hugWidth": True, "hugHeight": False}]}]}
    new, _ = migrations.size_modes(data, KIND.lists)
    g = new["comps"][0]["layers"][0]
    assert (g["sizeW"], g["sizeH"]) == ("fit", "fixed") and "hugWidth" not in g


def test_a_look_solves_only_its_frames_and_the_film_after_it_is_the_whole_bake():
    # A look's bake (layoutbake `frames`) is exact at its frames, and what it solved is kept: the export's whole bake
    # afterwards must be the same keys as one made from nothing, or a film drawn after a look moves boxes silently.
    src = 'with group("g", layout="row", gap=4):\n    shape("a", h=10, w=10).key("w", {0: 10, 1: 100})\n    shape("b", w=20, h=10)\n'
    comp, eng = _comp(src), FakeEngine()
    layout._answers.clear()
    layoutbake._KEPT.clear()
    with textsize.use(eng):
        part = layoutbake.bake(comp, 10, frames={3, 4})
        asked = sum(len(r) for r in eng.layouts)
        after = layoutbake.bake(comp, 10)
        layoutbake._KEPT.clear()
        layout._answers.clear()
        whole = layoutbake.bake(comp, 10)
    from rostrum_core.keys import track_value
    for item, fields in part.items():
        for prop, keys in fields.items():
            for t in (0.3, 0.4):
                assert track_value(keys, t) == track_value(whole[item][prop], t)
    assert {k["t"] for k in part["b"]["x"]} == {0.3, 0.4} and asked == 2
    assert after == whole
