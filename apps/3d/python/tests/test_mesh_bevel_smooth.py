"""Brief 8: a bevel and Smooth surface on an editable mesh survive save and reopen, and each undoes in one step."""
from rostrum_core import Document, Who

from rostrum3d import KIND, ops_mesh, run_source

from test_mesh_edit import SRC, drawn_box

SAM = Who.person()


def test_bevel_and_smooth_survive_reopening_and_undo_in_one_step_each(tmp_path):
    ops_mesh.use_geometry(drawn_box)
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("lid.py", run_source(SRC, "lid.py"))
    d.apply({"op": "mesh.edit", "target": ["lid"]}, SAM)
    box = d.item("lid")
    d.apply({"op": "edges.bevel", "target": ["lid"], "args": {"edges": "edges around top", "width": 0.001, "segments": 4}}, SAM)
    bevelled = d.item("lid")
    assert len(bevelled["faceCounts"]) > 6 + 4 * 4 - 1               # four rows of faces along each top edge
    d.apply({"op": "mesh.set", "target": ["lid"], "args": {"subdivide": 2}}, SAM)
    d.save()

    again = Document.open(tmp_path, "scene", KIND)
    lid = again.item("lid")
    assert lid["subdivide"] == 2
    assert (lid["points"], lid["faceIndices"]) == (bevelled["points"], bevelled["faceIndices"])
    again.undo(SAM)                                                   # Smooth surface: one step
    assert again.item("lid").get("subdivide", 0) == 0
    assert again.item("lid")["faceIndices"] == bevelled["faceIndices"]
    again.undo(SAM)                                                   # the bevel: one step
    assert again.item("lid")["faceIndices"] == box["faceIndices"]
