"""Imports (brief 29) where a slip would go unseen: a file in centimetres comes in at 1/100 with its base on the point,
its meshes listed as parts; Keep original size is one undo step that grows it around its base; the file's unit stays
the document's own (never sent to the core, which refuses unknown fields)."""
import pytest
from rostrum_core import Document, Who

from rostrum3d import KIND, ops_import, run_source
from rostrum3d.compile import describe

SAM = Who.person()
CRATE = {"format": "FBX", "metersPerUnit": 0.01, "unitsKnown": True, "upAxis": "Y", "defaultPrim": "/crate",
         "prims": [{"path": "/crate", "type": "Xform", "bounds": [[-20, 0, -20], [20, 45, 20]]},
                   {"path": "/crate/Box", "type": "Mesh", "bounds": [[-20, 0, -20], [20, 45, 20]]},
                   {"path": "/crate/Materials/Wood", "type": "Material"}]}
SRC = '''
cam = camera("cam", z=3)
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


@pytest.fixture
def doc():
    ops_import.use_inspect(lambda file: CRATE)
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    yield d
    ops_import.use_inspect(None)


def test_a_file_in_centimetres_lands_at_one_hundredth_on_its_base(doc):
    doc.apply({"op": "import.add", "args": {"id": "crate", "file": "C:/x/crate.fbx", "x": 1.0, "y": 0.6, "z": 0.0}}, SAM)
    it = doc.item("crate")
    assert (it["sx"], it["sy"], it["sz"], it["fileUnit"]) == (0.01, 0.01, 0.01, 0.01)
    assert (it["x"], it["y"], it["z"]) == pytest.approx((1.0, 0.6, 0.0))      # bounds start at y 0: base on the point
    assert [p["path"] for p in it["parts"]] == ["Box"]                       # meshes only, never the materials
    assert ops_import.unit_note(it) == "Imported at 1/100: it was in centimetres"
    assert "fileUnit" not in next(n for n in describe(doc.data, "hero")["items"] if n["id"] == "crate")["props"]


def test_keep_original_size_is_one_undo_step_around_the_base(doc):
    doc.apply({"op": "import.add", "args": {"id": "crate", "file": "C:/x/crate.fbx", "y": 0.6, "z": 0.5}}, SAM)
    doc.apply({"op": "import.keep_size", "target": ["crate"]}, SAM)
    it = doc.item("crate")
    assert (it["sy"], it["fileUnit"], ops_import.unit_note(it)) == (1.0, 1.0, "")
    assert (it["y"], it["z"]) == pytest.approx((0.6, 0.5))                   # 100 times bigger, still standing there
    doc.undo(SAM)
    assert (doc.item("crate")["sy"], doc.item("crate")["fileUnit"]) == (0.01, 0.01)


def test_keep_size_and_a_file_without_a_unit_are_not_rescaled(doc):
    doc.apply({"op": "import.add", "args": {"id": "a", "file": "C:/x/crate.fbx", "keepSize": True}}, SAM)
    ops_import.use_inspect(lambda file: {**CRATE, "unitsKnown": False, "metersPerUnit": 1.0})
    doc.apply({"op": "import.add", "args": {"id": "b", "file": "C:/x/crate.obj"}}, SAM)
    assert doc.item("a")["sy"] == doc.item("b")["sy"] == 1.0
    assert ops_import.unit_note(doc.item("a")) == ops_import.unit_note(doc.item("b")) == ""
