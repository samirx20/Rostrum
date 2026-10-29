"""Garments from patterns (PR7): what would break silently is a pattern mesh that leaves part of a piece out or has
slivers, seam pairs pointing at the wrong points (the engine sews whatever it is sent), a request body that changes every
older cloth's stored key, a mistake that is not refused, or a re-run that loses the garment."""
from __future__ import annotations

import math

import pytest
from rostrum_core import Document, Who
from rostrum_core.errors import RostrumError

from rostrum3d import KIND, garment, garment_mesh as GM, run_source
from rostrum3d.compile import describe
from rostrum3d.sim.inputs import sim_inputs

SAM = Who.person()
FRONT = [[-0.25, 0], [0.25, 0], [0.25, 0.5], [0.4, 0.55], [0.33, 0.7], [0.1, 0.72], [-0.1, 0.72], [-0.33, 0.7],
         [-0.4, 0.55], [-0.25, 0.5]]                      # a T-shirt-like front with sleeve stubs; edges 4 and 6 shoulders
BACK = [[-x, y] for x, y in FRONT]                       # its mirror (clockwise): turned 180, edge i is beside front's edge i
SHIRT = {"pieces": garment.text([{"name": "front", "outline": FRONT, "at": [0, 0.8, 0.12], "wrap": 0.25},
                                 {"name": "back", "outline": BACK, "at": [0, 0.8, -0.12], "turn": 180, "wrap": 0.25}]),
         "seams": garment.text([{"a": ["front", i], "b": ["back", i]} for i in (1, 2, 4, 6, 7, 9)])}
SRC = '''
cam = camera("cam", z=3, y=1)
shot("s", camera=cam, fps=10, start=0, end=1)
mesh("post", shape="cylinder", radius=0.12, height=1.2).simulate("still")
mesh("sheet", shape="plane", width=0.5, depth=0.5, y=1.5).simulate("cloth")
panel = [[-0.16, 0], [0.16, 0], [0.16, 0.35], [-0.16, 0.35]]
garment("wrapper", sewTime=0.6, pieces=[
    {"name": "front", "outline": panel, "at": [0, 0.6, 0.15], "wrap": 0.15},
    {"name": "back", "outline": panel, "at": [0, 0.6, -0.15], "turn": 180, "wrap": 0.15}],
  seams=[{"a": ["front", 1], "b": ["back", 3]}, {"a": ["front", 3], "b": ["back", 1]}])
'''


def _angles(points, tris):
    for t in tris:
        for k in range(3):
            a, b, c = (points[t[(k + i) % 3]] for i in range(3))
            u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            yield math.degrees(math.acos(sum(p * q for p, q in zip(u, v)) / math.hypot(*u) / math.hypot(*v)))


def test_each_piece_is_covered_by_well_shaped_triangles():
    flat = {"pieces": garment.text([{"name": "front", "outline": FRONT}, {"name": "back", "outline": BACK}]), "seams": ""}
    made = garment.make(flat)
    pts, tris = made["points"], made["triangles"]
    area = sum(abs(GM._orient(pts[a], pts[b], pts[c])) / 2 for a, b, c in tris)
    assert area == pytest.approx(2 * abs(GM.area2(FRONT)) / 2, rel=0.01)
    assert 7000 < len(pts) < 11000
    assert min(_angles(pts, tris)) > 20
    assert min(_angles(*map(garment.make(SHIRT).get, ("points", "triangles")))) > 20     # wrapped round: still no slivers


def test_seam_pairs_join_the_named_edges_end_to_end():
    made = garment.make(SHIRT)
    edges, pts = made["edges"], made["points"]
    pairs = {tuple(p) for p in made["seams"]}
    for i in (1, 2, 4, 6, 7, 9):
        a, b = edges["front"][i], edges["back"][i]
        mine = [p for p in made["seams"] if p[0] in a and p[1] in b]
        assert {p[0] for p in mine} == set(a) and {p[1] for p in mine} == set(b)   # every point of both edges is sewn
        straight = math.dist(pts[a[0]], pts[b[0]]) + math.dist(pts[a[-1]], pts[b[-1]])
        if math.dist(pts[a[0]], pts[b[-1]]) + math.dist(pts[a[-1]], pts[b[0]]) < straight:
            b = b[::-1]
        assert {(a[0], b[0]), (a[-1], b[-1])} <= pairs                # ends with ends, the nearer way round
    assert all(p[0] in {q for e in edges["front"] for q in e} for p in made["seams"])


@pytest.mark.parametrize("pieces, seams, words", [
    ([{"name": "a", "outline": [[0, 0], [1, 0]]}], [], "at least 3 points"),
    ([{"name": "a", "outline": [[0, 0], [1, 1], [1, 0], [0, 1]]}], [], "crosses itself"),
    ([{"name": "a", "outline": FRONT}], [{"a": ["a", 1], "b": ["b", 1]}], 'no piece "b"'),
    ([{"name": "a", "outline": FRONT}], [{"a": ["a", 1], "b": ["a", 10]}], "edges 0 to 9"),
    ([{"name": "a", "outline": FRONT}], [{"a": ["a", 1], "b": ["a", 3]}, {"a": ["a", 1], "b": ["a", 5]}], "sewn already"),
])
def test_a_pattern_mistake_is_refused_in_words(pieces, seams, words):
    with pytest.raises(garment.PatternError, match=words):
        garment.check(pieces, seams)
    with pytest.raises(RostrumError, match=words):
        run_source(f"garment('g', pieces={pieces!r}, seams={seams!r})", "s.py")


def test_the_request_sends_seams_and_sewing_time_only_for_a_pattern_and_a_rerun_keeps_it():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py", d))
    node = next(n for n in describe(d.data, "s", sim="none")["items"] if n["id"] == "wrapper")
    req, _ = sim_inputs(d.data, "s")
    body = {b["item"]: b for b in req["bodies"]}
    assert "seams" not in body["sheet"] and "sewTime" not in body["sheet"]          # older cloths keep their key
    assert body["wrapper"]["sewTime"] == 0.6 and body["wrapper"]["seams"] == garment.make(d.item("wrapper"))["seams"]
    assert node["props"]["shape"] == "poly" and len(node["props"]["points"]) == len(garment.make(d.item("wrapper"))["points"])
    assert "pieces" not in node["props"] and set(node["props"]["faceCounts"]) == {3}
    d.apply({"op": "mesh.set", "target": ["wrapper"], "args": {"clothWeight": 0.4}}, SAM)
    d.run_script("s.py", run_source(SRC.replace("sewTime=0.6", "sewTime=1.0"), "s.py", d))
    item = d.item("wrapper")
    assert item["shape"] == "pattern" and item["sewTime"] == 1.0 and item["clothWeight"] == 0.4


def test_the_operations_change_one_piece_or_seam_at_a_time():
    d = Document.new(KIND)
    sq = [[-0.2, 0], [0.2, 0], [0.2, 0.4], [-0.2, 0.4]]
    d.apply({"op": "garment.make", "args": {"id": "g", "pieces": garment.text([{"name": "front", "outline": sq}])}}, SAM)
    d.apply({"op": "garment.piece", "target": ["g"], "args": {"name": "back", "outline": sq, "turn": 180}}, SAM)
    d.apply({"op": "garment.sew", "target": ["g"], "args": {"aPiece": "front", "aEdge": 1, "bPiece": "back", "bEdge": 3}}, SAM)
    assert garment.read(d.item("g")["seams"], "seams") == [{"a": ["front", 1], "b": ["back", 3]}]
    with pytest.raises(RostrumError, match="edges 0 to 3"):
        d.apply({"op": "garment.sew", "target": ["g"], "args": {"aPiece": "front", "aEdge": 2, "bPiece": "back", "bEdge": 7}}, SAM)
    d.apply({"op": "garment.piece", "target": ["g"], "args": {"name": "back", "remove": True}}, SAM)
    assert d.item("g")["seams"] == "[]"                                        # its seams went with it
    with pytest.raises(RostrumError, match="Cloth"):
        d.apply({"op": "mesh.set", "target": ["g"], "args": {"simulate": "falls"}}, SAM)
