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
    assert [l["id"] for l in doc.data["comps"][0]["layers"]] == ["frame", "u"]


def test_path_width_refuses_a_bad_profile_and_is_one_undo_step():
    doc = _doc({"op": "layer.add", "target": ["c"], "args": {"type": "path", "id": "p"}})
    width = lambda **a: [{"op": "path.width", "target": ["p"], "args": a}]  # noqa: E731
    for bad in ({"profile": [[0, 1], [0.5, -1]]}, {"profile": [[0, 1], [0, 2]]}, {"profile": [[0, 1], [1.5, 1]]}):
        try:
            doc.apply(width(**bad), ME)
        except Exception as e:
            assert "profile" in str(e)
        else:
            raise AssertionError(f"{bad} was accepted")
    try:
        doc.apply(width(taperEnd=0.3), ME)       # stroke is off: the width would show nothing
    except Exception as e:
        assert "stroke" in str(e)
    else:
        raise AssertionError("a width on a path with its stroke off was accepted")
    doc.apply([{"op": "path.set", "target": ["p"], "args": {"stroke": True}}], ME)
    doc.apply(width(taperEnd=0.3, profile=[[0, 0.5], [0.5, 2]]), ME)
    assert (doc.item("p")["taperEnd"], doc.item("p")["widthProfile"]) == (0.3, "0,0.5 0.5,2")
    doc.undo(ME)
    assert (doc.item("p")["taperEnd"], doc.item("p")["widthProfile"]) == (0.0, "")


def test_any_svg_path_data_is_taken_and_kept_as_m_l_c_z():
    """FRICTION A3-2: relative commands, H / V, Q / T, S and arcs are read as SVG reads them (script, path.set, a d key)
    and kept as absolute M L C Z; anything SVG does not read is refused loudly."""
    import math
    import pytest
    from rostrum2d import run_source
    assert PD.normalize("m10 10 l20 0 h10 v10 H0 V0 z") == "M 10 10 L 30 10 L 40 10 L 40 20 L 0 20 L 0 0 Z"
    assert PD.normalize("M0 0 Q50 -50 100 0 T200 0") == "M 0 0 C 33.333 -33.333 66.667 -33.333 100 0 C 133.333 33.333 166.667 33.333 200 0"
    assert PD.normalize("M0 0 C10 0 20 10 20 20 s10 20 20 20") == "M 0 0 C 10 0 20 10 20 20 C 20 30 30 40 40 40"
    arc = PD.commands(PD.normalize("M0 0 A50 50 0 0 1 100 0"))             # a half circle round (50, 0), over the top
    assert PD.bounds(arc) == pytest.approx((0, -50, 100, 0), abs=0.01)
    mid = arc[1][5:7]
    assert math.hypot(mid[0] - 50, mid[1]) == pytest.approx(50, abs=0.01)
    assert PD.normalize(CURVY) == CURVY                                        # already stored form: untouched
    for bad, said in (("M0 0 X 4", '"X" is not an SVG path command'), ("M0 0 Q1 2", "Q needs 4 numbers"),
                      ("10 10", "before a command"), ("M0 0 A10 10 0 2 1 5 5", "arc flag is 0 or 1")):
        with pytest.raises(ValueError, match=said):
            PD.normalize(bad)
    doc = _doc({"op": "layer.add", "target": ["c"], "args": {"type": "path", "id": "p"}},
               {"op": "path.set", "target": ["p"], "args": {"d": "M0 0 h100 v100 z"}},
               {"op": "key.add", "target": ["p"], "args": {"prop": "d", "t": 1, "d": "M0 0 q50 50 100 0 z"}})
    assert doc.item("p")["d"] == "M 0 0 L 100 0 L 100 100 Z"
    assert doc.item("p")["keys"][0]["d"].startswith("M 0 0 C ")
    src = 'comp("c")\np = path("q", d="M100 100 q50 -50 100 0", fill="none", stroke=True)\np.key("d", {0: "M100 100 h100", 1: "M100 100 l100 20"})\n'
    d2 = Document.new(KIND)
    d2.run_script("s.py", run_source(src, "s.py"))
    assert all(set(PD.commands(k["d"])[1][0]) <= {"L"} for k in d2.item("q")["keys"])
    assert d2.item("q")["d"].startswith("M 0 ")
