"""Editable mesh, part 2 (SPEC §4.3): bevelling a box's top edge loop and loop-cutting it keep the mesh closed and
welded (every edge between exactly two faces), and the per-face materials always match the faces."""
from rostrum_core import Document, Who

from rostrum3d import KIND, ops_mesh, run_source
from rostrum3d.mesh_book import edge_set
from rostrum3d.poly import faces_of
from test_mesh_edit import SRC, drawn_box

SAM = Who.person()


def closed(item) -> bool:
    count = {}
    for f in faces_of(item):
        for a, b in zip(f, f[1:] + f[:1]):
            count[a, b] = count.get((a, b), 0) + 1
    return all(n == 1 and count.get((b, a)) == 1 for (a, b), n in count.items())


def matched(item) -> bool:
    return item["faceMaterials"] == [] or len(item["faceMaterials"]) == len(item["faceCounts"])


def test_bevel_and_loop_cut_keep_the_mesh_closed_and_materials_matched(tmp_path):
    ops_mesh.use_geometry(drawn_box)
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("lid.py", run_source(SRC + 'material("red")\n', "lid.py"))
    d.apply({"op": "mesh.edit", "target": ["lid"]}, SAM)
    d.apply({"op": "faces.material", "target": ["lid"], "args": {"faces": "top", "material": "red"}}, SAM)
    lid = d.item("lid")
    top = sorted(f for f in faces_of(lid) if len(f) == 4 and all(lid["points"][v][1] > 0 for v in f))[0]
    loop = " ".join(f"{a}-{b}" for a, b in zip(top, top[1:] + top[:1]))
    d.apply({"op": "edges.sharp", "target": ["lid"], "args": {"edges": "edges " + loop.split()[0]}}, SAM)

    out = d.apply({"op": "edges.bevel", "target": ["lid"],
                   "args": {"edges": "edges " + loop, "width": 0.001, "segments": 4}}, SAM)
    lid = d.item("lid")
    assert closed(lid) and matched(lid)
    assert len(lid["points"]) == 4 + 4 * 5          # the bottom 4; per top corner: inner, side and 3 round points
    assert len(lid["faceCounts"]) == 6 + 4 * 4
    assert lid["faceMaterials"].count("red") == 1 + 4 * 2     # the top and the top half of each round
    assert lid["creases"] == []                      # the sharp edge was bevelled away
    assert out is not None

    d.apply({"op": "edges.sharp", "target": ["lid"], "args": {"edges": "edges " + _vertical(lid)}}, SAM)
    d.apply({"op": "edges.loopcut", "target": ["lid"], "args": {"edges": "edges " + _vertical(lid), "count": 2}}, SAM)
    lid = d.item("lid")
    assert closed(lid) and matched(lid)
    assert len(lid["creases"]) == 2 * 3              # the sharp edge, cut twice, is three sharp pieces
    pairs = zip(lid["creases"][0::2], lid["creases"][1::2])
    assert all((min(a, b), max(a, b)) in edge_set(faces_of(lid)) for a, b in pairs)

    d.apply({"op": "faces.extrude", "target": ["lid"], "args": {"faces": "bottom", "distance": -0.001}}, SAM)
    assert closed(d.item("lid")) and matched(d.item("lid"))


def _vertical(item) -> str:
    """An edge from the bottom to the round (a side face's upright edge)."""
    pts = item["points"]
    for a, b in edge_set(faces_of(item)):
        if abs(pts[a][0] - pts[b][0]) < 1e-9 and abs(pts[a][2] - pts[b][2]) < 1e-9 and min(pts[a][1], pts[b][1]) < 0:
            return f"{a}-{b}"
    raise AssertionError("no upright edge")
