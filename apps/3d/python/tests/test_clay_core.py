"""Clay through the built core: the same steps give the same clay after the project is saved and opened again in a
fresh engine (its shape's hash), whether the core replays the steps or reads its cache. Skipped until the core is
built (the lead runs it)."""
import pytest
from rostrum_core import Document, Who

from rostrum3d import KIND
from rostrum3d.compile import describe
from rostrum3d.runtime import find_exe

SAM = Who.person()
DABS = [[0.0, 0.02, 0.1, 0.0, 0.2, 0.98, 0.0, 0.0, 0.0], [0.01, 0.02, 0.1, 0.1, 0.2, 0.97, 0.0, 0.0, 0.0]]


def _hash(doc, folder) -> dict:
    from rostrum3d.engine import Engine
    with Engine() as engine:
        engine.ensure_scene(describe(doc.data, "hero", folder))
        return engine.clay_info("head")


def test_same_steps_same_clay_after_reopen(tmp_path):
    if not find_exe().exists():
        pytest.skip("3D engine not built")
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.apply([{"op": "camera.add", "args": {"id": "cam", "z": 1.0}},
             {"op": "shot.add", "args": {"id": "hero", "camera": "cam"}},
             {"op": "clay.add", "args": {"id": "head", "at": [0, 0, 0], "radius": 0.1}}], SAM)
    d.apply({"op": "clay.lump", "target": ["head"], "args": {"at": [0.06, 0.02, 0.05], "radius": 0.03}}, SAM)
    d.apply({"op": "clay.stroke", "target": ["head"], "args": {"dabList": DABS, "brush": "carve"}}, SAM)
    d.apply({"op": "clay.stroke", "target": ["head"],
             "args": {"path": [[-0.05, 0.03, 0.3], [0.05, 0.03, 0.3]], "dir": [0, 0, -1], "size": 0.015}}, SAM)
    d.save()
    first = _hash(d, tmp_path)
    again = _hash(Document.open(tmp_path, "scene", KIND), tmp_path)
    assert first["ok"] and first["steps"] == 4 and first["voxels"] > 0
    assert again["hash"] == first["hash"]
