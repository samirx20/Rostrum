"""A hugging group keeps its left edge when it grows (the lower-third bug: it spread both ways off the picture), and an
older file's hugging group keeps drawing as it did (silent look change otherwise)."""
import copy

from rostrum_core import Document, Who

from rostrum2d import KIND, layout, run_source, textsize
from fake_layout import FakeEngine

SRC = '''
comp("c", width=1000, height=400, fps=10, duration=1)
with group("g", x=300, y=200, w=200, h=100, layout="row", padding=0, sizeW="fit", sizeH="fit",
           hugPin=True) as g:
    shape("a", w=200, h=100)
g.key("w", {0: 200})
'''


def _group(src=SRC):
    d = Document.new(KIND)
    with textsize.use(FakeEngine()):
        d.run_script("a.py", run_source(src, "a.py"))
    return d, d.item("g")


def _solve(comp):
    with textsize.use(FakeEngine()):
        return layout.solve(comp, 0.0)


def _left(d, w):
    d.apply({"op": "shape.set", "target": "a", "args": {"w": w}}, Who.person("sam"))
    comp = d.item("c")
    out = _solve(comp)["g"]
    return out.get("x", 300) - 0.5 * out["w"], out


def test_growing_hug_keeps_left_and_top_and_old_files_keep_their_look():
    d, g = _group()
    assert g["hugPin"] is True
    left0 = g["x"] - g["anchorX"] * g["w"]
    left, out = _left(d, 600)
    assert abs(left - left0) < 1e-6 and out["w"] == 600
    data = copy.deepcopy(d.data)                                     # an older file: no hugPin on its group
    grp = data["comps"][0]["layers"][1]
    del grp["hugPin"]
    new, _ = KIND.upgrade(data, KIND.lists)
    assert new["comps"][0]["layers"][1]["hugPin"] is False
    assert abs(_solve(new["comps"][0])["g"].get("x", 300) - 300) < 1e-6   # old look: grows round the anchor
    assert KIND.upgrade(new, KIND.lists) is None


def test_auto_layout_hugs_by_default_and_old_files_keep_their_size():
    d, g = _group('comp("c", width=1000, height=400, fps=10, duration=1)\nwith group("g", layout="row", padding=10):\n    shape("a", w=200, h=100)\n')
    assert _solve(d.item("c"))["g"]["w"] == 220                  # no switch touched: the box hugs its layers, 10 px padding
    data = copy.deepcopy(d.data)                                            # an older file: the group has no hug fields
    for k in ("sizeW", "sizeH"):
        data["comps"][0]["layers"][1].pop(k, None)
    new, _ = KIND.upgrade(data, KIND.lists)
    grp = new["comps"][0]["layers"][1]
    assert grp["sizeW"] == "fixed" and grp["sizeH"] == "fixed"
