"""Expressions on a field (expr.py, exprbake.py, ops_expr.py): they can only do what the fixed grammar allows (never
Python), a loop is refused when set and again when drawn, the baked keys are exact at every frame, and undo takes
an expression back out."""
import copy

import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, run_source
from rostrum2d.expr import parse
from rostrum2d.expr_lib import noise
from rostrum2d.scene import describe

SAM = Who.person("sam")
SRC = '''
comp("c", width=320, height=180, fps=10, duration=2)
logo = shape("logo", x=100, w=10, h=10)
logo.key("x", {0: 100, 1: 200}, ease="linear")
a = shape("a", w=10, h=10)
a.link("x", of="logo", field="x", scale=2, offset=10)
a.expr("y", "50 + 10 * time + noise(0)")
b = shape("b", w=10, h=10)
b.expr("opacity", "clamp(ref('a.x', time - 0.1) / 1000, 0, 1) if frame > 1 else 0")
'''


def doc():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    return d


def anim(scene, id_, prop):
    layer = next(c for c in scene["comp"]["layers"] if c["id"] == id_)
    return layer["anim"][prop]


@pytest.mark.parametrize("src", ["__import__('os')", "open(1)", "logo.x.__class__", "(1).real", "lambda: 1", "[1]",
                                 "'abc'", "sin", "foo(1)", "1 +", "sin(1, 2)"])
def test_the_parser_only_takes_its_own_grammar(src):
    with pytest.raises(RostrumError, match="column"):
        doc().apply({"op": "expr.set", "target": "b", "args": {"prop": "x", "source": src}}, SAM)
    assert parse("sin(time) + a.x * 2") and parse("-2 ^ 2 if frame >= 1 else min(1, 2)")   # what it does take


def test_unknown_function_names_the_column_and_the_field():
    d = doc()
    with pytest.raises(RostrumError, match=r"b\.x: column 5: unknown function \"eval\""):
        d.apply({"op": "expr.set", "target": "b", "args": {"prop": "x", "source": "1 + eval(2)"}}, SAM)


def test_a_loop_is_refused_when_set_and_when_drawn():
    d = doc()
    with pytest.raises(RostrumError, match=r"loop: logo\.x <- a\.x <- logo\.x"):
        d.apply({"op": "expr.set", "target": "logo", "args": {"prop": "x", "source": "a.x"}}, SAM)
    sneaky = copy.deepcopy(d.data)             # written behind the operations' back (a hand-edited file)
    logo = next(i for i in sneaky["comps"][0]["layers"] if i["id"] == "logo")
    logo["exprs"].append({"id": "logo.x.expr", "type": "expr", "prop": "x", "source": "a.x"})
    with pytest.raises(ValueError, match="loop"):
        describe(sneaky)


def test_bind_and_expression_are_baked_exactly_at_every_frame():
    scene = describe(doc().data)
    x = anim(scene, "a", "x")
    assert len(x) == 21 and all(k["ease"] == "linear" for k in x)
    assert (x[0]["v"], x[5]["v"], x[10]["v"], x[20]["v"]) == (210.0, 310.0, 410.0, 410.0)   # logo.x * 2 + 10
    y = anim(scene, "a", "y")
    assert y[10]["v"] == pytest.approx(60 + noise(0)) and y[10]["t"] == 1.0
    op = anim(scene, "b", "opacity")                 # a.x one tenth of a second earlier, from frame 2 on
    assert op[1]["v"] == 0 and op[5]["v"] == pytest.approx(0.29)         # (100 + 40) * 2 + 10 = 290 at 0.4 s


def test_undo_takes_an_expression_back_out():
    d = doc()
    before = copy.deepcopy(d.data)
    d.apply({"op": "expr.set", "target": "b", "args": {"prop": "x", "source": "a.x + 5"}}, SAM)
    assert anim(describe(d.data), "b", "x")[0]["v"] == 215.0
    d.undo(SAM)
    assert d.data == before and "x" not in next(c for c in describe(d.data)["comp"]["layers"] if c["id"] == "b").get("anim", {})
