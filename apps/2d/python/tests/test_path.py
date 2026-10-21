"""Paths: a point edit changes only that point (d survives the round trip through points), and a boolean's result
sits exactly where its inputs were drawn. Both would go wrong silently (a shifted or reshaped path still draws)."""
from rostrum_core import Document
from rostrum_core.who import Who

from rostrum2d import pathdata as PD
from rostrum2d.kind import KIND

ME = Who.agent("test")
CURVY = "M 0 0 L 100 0 C 150 0 150 100 100 100 L 0 100 Z M 10 10 C 20 0 30 0 40 10"


def _doc(*calls):
    doc = Document.new(KIND)
    doc.apply([{"op": "comp.add", "args": {"id": "c"}}, *calls], ME)
    return doc


def test_a_point_edit_changes_only_that_point():
    assert PD.from_points(PD.to_points(CURVY)) == CURVY
    doc = _doc({"op": "layer.add", "target": ["c"], "args": {"type": "path", "id": "p"}},
               {"op": "path.set", "target": ["p"], "args": {"d": CURVY}})
    doc.apply([{"op": "path.set_point", "target": ["p"], "args": {"i": 1, "x": 90, "y": 5}}], ME)
    assert doc.item("p")["d"] == CURVY.replace("L 100 0 C 150 0", "L 90 5 C 140 5", 1)


def test_a_boolean_result_sits_where_its_inputs_were():
    doc = _doc(*[c for id_, x, rot in (("a", 300, 90), ("b", 700, 0)) for c in (
        {"op": "layer.add", "target": ["c"], "args": {"type": "shape", "id": id_}},
        {"op": "shape.set", "target": [id_], "args": {"x": x, "y": 500, "w": 200, "h": 100, "rotation": rot}})])
    doc.apply([{"op": "path.boolean", "target": ["a", "b"], "args": {"mode": "union", "id": "u"}}], ME)
    u = doc.item("u")
    # a: 200 × 100 turned a quarter about its centre (300, 500) → x 250..350, y 400..600; b: x 600..800, y 450..550
    assert [round(u[k], 3) for k in ("x", "y", "w", "h")] == [525.0, 500.0, 550.0, 200.0]
    assert [l["id"] for l in doc.data["comps"][0]["layers"]] == ["u"]
