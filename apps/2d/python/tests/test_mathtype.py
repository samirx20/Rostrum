"""Typeset maths (mathtype.py): math_text and math.add make a group of ordinary path layers with real path data
(one per symbol and rule), and a bad formula is refused loudly."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.tree import walk

from rostrum2d import KIND, run_source

TEX = r"f(x)=\frac{4}{\pi}\sum_{k=1}^{\infty}\frac{\sin((2k-1)x)}{2k-1}"


def _paths(root, group):
    return [i for i in walk(root, KIND.lists) if i.get("type") == "path" and i["id"].startswith(group + "_")]


def test_script_call_makes_path_layers_with_geometry():
    root = run_source(f'comp("c", width=800, height=300, duration=1)\nmath_text("eq", r"{TEX}", x=40, y=40, size=60)', "t.py")
    paths = _paths(root, "eq")
    assert len(paths) >= 25 and all(p["d"].startswith("M") and p["w"] > 0 for p in paths)
    ids = [p["id"] for p in paths]
    assert "eq_5_equal" in ids and any(i.endswith("_sum") for i in ids) and sum(i.endswith("_bar") for i in ids) == 2


def test_operation_makes_the_same_layers():
    d = Document.new(KIND)
    d.run_script("t.py", run_source('comp("c", width=800, height=300, duration=1)', "t.py"))
    comp = d.data["comps"][0]["id"]
    d.apply([{"op": "math.add", "target": [comp], "args": {"tex": r"\frac{1}{2}", "id": "half", "size": 80}}], Who.agent("t"))
    assert [p["id"] for p in _paths(d.data, "half")] == ["half_1_1", "half_2_bar", "half_3_2"]


def test_bad_latex_fails_loudly():
    with pytest.raises(Exception, match=r"can't typeset"):
        run_source('comp("c", width=100, height=100, duration=1)\nmath_text("e", r"\frac{1")', "t.py")
