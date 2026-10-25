"""Select first, then act (ops_group, ops_mask, ops_align): grouping and ungrouping leave every layer where it was and
undo in one step; a mask links the cutter to what it cuts; align moves layers to a shared edge."""
import copy

import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, boxes, fields as F
from rostrum2d.ops_path import to_parent

SAM = Who.person("sam")


@pytest.fixture
def doc():
    d = Document.new(KIND)
    calls = [{"op": "comp.add", "args": {"id": "film"}}]
    for id_, x, y, w, h in (("a", 300, 300, 100, 100), ("b", 700, 500, 200, 100), ("c", 900, 200, 60, 60)):
        calls += [{"op": "layer.add", "target": "film", "args": {"type": "shape", "id": id_}},
                  {"op": "shape.set", "target": id_, "args": {"x": x, "y": y, "w": w, "h": h}}]
    d.apply(calls, SAM)
    return d


def _where(d):
    return {i: boxes.box(d.item(i)) for i in ("a", "b", "c") if d.has(i)}


def test_group_then_release_keeps_every_layer_in_place_and_undoes(doc):
    before, data = _where(doc), copy.deepcopy(doc.data)
    doc.apply({"op": "group.make", "target": ["a", "b"], "args": {"id": "pair"}}, SAM)
    g = doc.item("pair")
    assert [c["id"] for c in g["layers"]] == ["a", "b"] and (g["x"], g["y"], g["w"], g["h"]) == (525, 400, 550, 300)
    assert _where(doc)["a"] != before["a"]                                      # inside the group it is in the group's px
    doc.apply({"op": "group.release", "target": "pair", "args": {}}, SAM)
    assert not doc.has("pair") and [l["id"] for l in doc.item("film")["layers"]] == ["frame", "a", "b", "c"]
    assert _where(doc) == before
    doc.undo(SAM)
    doc.undo(SAM)
    assert doc.data == data


def test_release_bakes_a_scaled_group(doc):
    doc.apply([{"op": "group.make", "target": ["a", "b"], "args": {"id": "pair"}},
               {"op": "group.set", "target": "pair", "args": {"scale": 2.0}}], SAM)
    g = F.defaults("group") | doc.item("pair")
    on_screen = to_parent(g)(doc.item("a")["x"], doc.item("a")["y"])
    doc.apply({"op": "group.release", "target": "pair", "args": {}}, SAM)
    a = doc.item("a")
    assert (a["x"], a["y"], a["scale"]) == (on_screen[0], on_screen[1], 2.0)


def test_release_refuses_what_would_jump(doc):
    doc.apply({"op": "group.make", "target": ["a", "b"], "args": {"id": "pair"}}, SAM)
    doc.apply({"op": "effect.add", "target": "pair", "args": {"type": "blur"}}, SAM)
    with pytest.raises(RostrumError, match="effects or masks"):
        doc.apply({"op": "group.release", "target": "pair", "args": {}}, SAM)


def test_mask_make_links_the_cutter_and_align_left(doc):
    doc.apply({"op": "mask.make", "target": ["a"], "args": {"cutter": "c", "mode": "luma"}}, SAM)
    a = doc.item("a")
    assert (a["matte"], a["matteMode"]) == ("c", "luma") and doc.item("c").get("matte", "") == ""
    assert {l["id"] for l in doc.item("film")["layers"][-1]["layers"]} == {"a", "c"}
    doc.apply({"op": "mask.release", "target": ["a"], "args": {}}, SAM)
    assert doc.item("a")["matte"] == ""


def test_align_left_moves_layers_to_one_edge(doc):
    doc.apply({"op": "layer.align", "target": ["a", "b"], "args": {"edge": "left"}}, SAM)
    assert boxes.box(doc.item("a"))[0] == boxes.box(doc.item("b"))[0] == 250


def test_distribute_with_a_typed_gap_spaces_them_exactly_in_one_undo_step(doc):
    data = copy.deepcopy(doc.data)
    doc.apply({"op": "layer.distribute", "target": ["c", "a", "b"], "args": {"axis": "x", "gap": 40}}, SAM)
    a, b, c = (boxes.box(doc.item(i)) for i in "abc")
    assert a[0] == 250 and b[0] - a[2] == 40 and c[0] - b[2] == 40          # from the leftmost, which stays
    doc.undo(SAM)
    assert doc.data == data
