"""A file naming a font this computer lacks: the canvas still draws everything (the text as a dashed red box with the font's
name), a whole-film export refuses naming the texts, and "Use another font" is one change (one undo step) for all of them."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, run_source
from rostrum2d.scene import describe

SAM = Who.person("sam")
SRC = 'comp("c", width=320, height=180, fps=10, duration=2)\nshape("a", w=10, h=10)\ntext("t1", body="One")\ntext("t2", body="Two")\n'


def _doc():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    for t in d.data["comps"][0]["layers"]:
        if t["type"] == "text":
            t["font"] = "No Such Sans"          # as an opened file can name one: set directly, never through an operation
    return d


def test_looks_draw_a_placeholder_and_an_export_refuses_naming_the_texts():
    layers = {n["id"]: n for n in describe(_doc().data, span=(0.0, 2.0))["comp"]["layers"]}
    assert layers["a"]["type"] == "shape" and layers["t1"]["type"] == "group" and layers["t2"]["type"] == "group"
    assert any(n["props"].get("dash") for n in layers["t1"]["layers"]) and layers["t1"]["layers"][1]["props"]["body"] == "No Such Sans"
    with pytest.raises(RostrumError) as e:
        describe(_doc().data)                    # no span: a whole-film export
    assert "t1" in str(e.value) and "t2" in str(e.value) and "No Such Sans" in str(e.value)


def test_one_font_replacement_is_one_undo_step():
    d = _doc()
    d.apply({"op": "font.replace", "args": {"from": "No Such Sans", "to": "Roboto Flex"}}, SAM)
    assert {t["font"] for t in d.data["comps"][0]["layers"] if t["type"] == "text"} == {"Roboto Flex"}
    d.undo(SAM)
    assert {t["font"] for t in d.data["comps"][0]["layers"] if t["type"] == "text"} == {"No Such Sans"}
