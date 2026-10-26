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


def test_the_clay_you_let_go_of_is_the_clay_you_saw(tmp_path):
    """A live stroke, Build up off and on: the clay while the stroke is drawn (its hash) is the clay kept when it ends
    (CL2b: the end re-applied the stroke differently, and a ridge seen while dragging was half gone, or all)."""
    if not find_exe().exists():
        pytest.skip("3D engine not built")
    from rostrum3d.engine import Engine
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.apply([{"op": "camera.add", "args": {"id": "cam", "z": 1.0}},
             {"op": "shot.add", "args": {"id": "hero", "camera": "cam"}},
             {"op": "clay.add", "args": {"id": "ball", "at": [0, 0, 0], "radius": 0.1}}], SAM)
    cam = {"eye": [0, 0.05, 0.45], "target": [0, 0, 0], "fov": 35, "frame": 0, "width": 640, "height": 480}
    with Engine() as engine:
        engine.ensure_scene(describe(d.data, "hero", tmp_path))
        for accumulate in (False, True):
            engine.sculpt(item="ball", phase="begin", brush="add", size=0.025, strength=0.5, mirror=False,
                          accumulate=accumulate, points=[[220, 240]], **cam)
            for x in range(224, 420, 4):
                engine.sculpt(item="ball", phase="dab", points=[[x, 240]], **cam)
            seen = engine.clay_info("ball")["hash"]
            engine.sculpt(item="ball", phase="end", folder=str(tmp_path), points=[], **cam)
            assert engine.clay_info("ball")["hash"] == seen, f"Build up {'on' if accumulate else 'off'}"
