"""An editable mesh (SPEC §4.3): making a box editable and each edit after it is one undo step, and the edited mesh
survives save and reopen. The geometry comes from a stand-in for the engine (the core's own box, as drawn: one vertex
per face corner, so the weld is exercised too)."""
from rostrum_core import Document, Who

from rostrum3d import KIND, ops_mesh, run_source
from rostrum3d.mesh_select import parse

SAM = Who.person()
SRC = '''
mesh("lid", shape="box", width=0.064, height=0.01, depth=0.048)
cam = camera("cam", z=0.4)
shot("hero", camera=cam, fps=24, start=0, end=1)
'''
W, H, D = 0.032, 0.005, 0.024
CORNERS = [[x, y, z] for x in (-W, W) for y in (-H, H) for z in (-D, D)]
QUADS = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]   # outward, anticlockwise


def drawn_box(doc, id_):
    pts = [CORNERS[i] for q in QUADS for i in q]                 # unwelded, as the core draws hard edges
    return {"points": pts, "faceCounts": [4] * 6, "faceIndices": list(range(24))}


def test_editing_a_mesh_is_one_step_each_and_survives_reopening(tmp_path):
    ops_mesh.use_geometry(drawn_box)
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("lid.py", run_source(SRC, "lid.py"))
    d.apply({"op": "mesh.edit", "target": ["lid"]}, SAM)
    lid = d.item("lid")
    assert (lid["shape"], len(lid["points"]), lid["faceCounts"]) == ("poly", 8, [4] * 6)

    d.apply({"op": "faces.extrude", "target": ["lid"], "args": {"faces": "top", "distance": 0.002}}, SAM)
    lid = d.item("lid")
    assert len(lid["faceCounts"]) == 10 and abs(max(p[1] for p in lid["points"]) - (H + 0.002)) < 1e-9
    assert parse("top", lid)[1] == {3}                           # the pushed face is still the top

    d.undo(SAM)                                                  # the extrude is one step
    assert max(p[1] for p in d.item("lid")["points"]) == H
    d.redo(SAM)
    d.save()

    again = Document.open(tmp_path, "scene", KIND)
    assert again.item("lid")["points"] == d.item("lid")["points"]
    assert again.item("lid")["faceIndices"] == d.item("lid")["faceIndices"]
    again.undo(SAM)
    again.undo(SAM)                                              # making it editable was one step too
    assert again.item("lid")["shape"] == "box"
