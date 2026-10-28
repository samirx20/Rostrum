"""Placing by relation in a script: a layer with no x / y sits at its parent's centre (not a fixed 960, 540 off a
group's box or a portrait comp), a script's hugging group grows round its anchor while the canvas's still keeps its
top-left, and the pivot takes names (a typo lists them, not "Did you mean anchorY?")."""
import pytest

from rostrum_core import Document, Who

from rostrum2d import KIND, layout, run_source, textsize
from fake_layout import FakeEngine


def _layers(src):
    with textsize.use(FakeEngine()):
        comp = run_source(src, "a.py")["comps"][0]
    return comp, {n["id"]: n for n in comp["layers"]}


def test_no_x_y_is_the_parents_centre():
    _, ls = _layers('comp("c", width=1080, height=1920)\nshape("s")\nwith group("g", x=300, y=200, w=400, h=300):\n'
                    '    shape("in", w=50, h=50)')
    assert (ls["s"]["x"], ls["s"]["y"]) == (540, 960)
    assert (ls["g"]["layers"][0]["x"], ls["g"]["layers"][0]["y"]) == (200, 150)


def test_script_column_stays_centred_canvas_group_keeps_top_left():
    comp, ls = _layers('comp("c")\nwith group("col", x=960, y=540, layout="column", gap=24, align="center"):\n'
                       '    shape("a", w=120, h=120)\n    shape("b", w=200, h=40)')
    assert ls["col"]["hugPin"] is False
    with textsize.use(FakeEngine()):
        out = layout.solve(comp, 0.0)["col"]
    assert out.get("x", 960) == 960 and out.get("y", 540) == 540        # grows round its centre, no slide to the top
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "c"}}, {"op": "layer.add", "target": "c", "args": {"type": "group", "id": "g"}}],
            Who.person("sam"))
    assert d.item("g")["hugPin"] is True                                # the person's canvas keeps its top-left


def test_anchor_names_and_pairs():
    _, ls = _layers('comp("c")\ntext("a", body="x", anchor="left")\nshape("b", origin="bottom-right")\n'
                    'shape("p", anchor=(0, 1))')
    assert (ls["a"]["anchorX"], ls["a"]["anchorY"]) == (0, 0.5)
    assert (ls["b"]["anchorX"], ls["b"]["anchorY"]) == (1, 1)
    assert (ls["p"]["anchorX"], ls["p"]["anchorY"]) == (0, 1)
    with pytest.raises(Exception, match="top-left") as e:
        _layers('comp("c")\ntext("t", body="x", anchor="middle-ish")')
    assert "anchorY" not in str(e.value)


def test_a_container_with_no_place_sits_centred():
    _, ls = _layers('comp("c")\nwith column("free"):\n    shape("a", w=10, h=10)\nwith row("put", x=40, y=60):\n    shape("b", w=10, h=10)')
    assert (ls["free"]["x"], ls["free"]["y"], ls["free"]["anchorX"], ls["free"]["anchorY"]) == (960, 540, 0.5, 0.5)
    assert (ls["put"]["anchorX"], ls["put"]["anchorY"]) == (0, 0)          # x / y given: its top-left, as CSS


def test_a_letter_by_letter_text_goes_in_a_row_as_its_own_line():
    comp, _ = _layers('comp("c")\nwith row("r", gap=20):\n    text("a", body="Every", letterDelay=0.05)\n'
                      '    text("b", body="frame", letterDelay=0.05)')
    with textsize.use(FakeEngine()):
        out = layout.solve(comp, 0.0)
    assert "boxWidth" not in out["a"] and out["b"]["x"] > out["a"]["x"]   # no wrap asked of it: the engine can't draw that
