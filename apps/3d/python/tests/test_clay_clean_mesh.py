"""Make a clean mesh (PR4): the clay's surface becomes a new mesh of four-sided faces beside it, with the clay's place
and material, the clay hidden; one undo step takes all of it back; the same surface and count again comes from the
cache (no second rebuild); a Cancel ends the worker and leaves nothing in the cache."""
import math

import pytest
from rostrum_core import Document, Who
from rostrum_core.cache import Cache

from rostrum3d import KIND, ops_mesh, remesh

SAM = Who.person()


def sphere(doc, id_, n=40):
    pts = [[math.sin(math.pi * i / n) * math.cos(2 * math.pi * j / (2 * n)) * 0.1,
            math.cos(math.pi * i / n) * 0.1,
            math.sin(math.pi * i / n) * math.sin(2 * math.pi * j / (2 * n)) * 0.1] for i in range(n + 1) for j in range(2 * n)]
    idx, w = [], 2 * n
    for i in range(n):
        for j in range(w):
            a, b, c, d = i * w + j, i * w + (j + 1) % w, (i + 1) * w + j, (i + 1) * w + (j + 1) % w
            idx += [a, c, b, b, c, d]
    return {"points": pts, "faceCounts": [3] * (len(idx) // 3), "faceIndices": idx}


@pytest.fixture
def cache(tmp_path, monkeypatch):
    c = Cache(tmp_path / "cache")
    monkeypatch.setattr(remesh, "CACHE", c)
    remesh._LAST.clear()
    ops_mesh.use_geometry(sphere)
    yield c
    ops_mesh.use_geometry(None)


def test_clean_mesh_is_one_step_and_kept(cache):
    pytest.importorskip("pyinstantmeshes")
    d = Document.new(KIND)
    d.apply({"op": "clay.add", "args": {"id": "head", "at": [0, 1, 0], "radius": 0.1}}, SAM)
    d.apply({"op": "clay.set", "target": ["head"], "args": {"x": 0.5}}, SAM)
    d.apply({"op": "clay.clean_mesh", "target": ["head"], "args": {"faces": 800}}, SAM)
    meshes = [i for i in d.data["items"] if i["type"] == "mesh"]
    assert len(meshes) == 1
    m = meshes[0]
    assert set(m["faceCounts"]) == {4} and 500 < len(m["faceCounts"]) < 1200
    assert m["name"] == "Clay mesh" or m["name"].endswith(" mesh")
    assert m["x"] == d.item("head")["x"] and m["material"] == d.item("head")["material"]
    assert d.item("head")["visible"] is False
    d.undo(SAM)                                                   # one step: the mesh gone, the clay shown again
    assert not [i for i in d.data["items"] if i["type"] == "mesh"]
    assert d.item("head").get("visible", True) is True
    puts = cache.puts
    d.apply({"op": "clay.clean_mesh", "target": ["head"], "args": {"faces": 800}}, SAM)
    assert cache.puts == puts                                     # found in the cache: not rebuilt


def test_cancel_ends_the_worker_and_keeps_nothing(cache):
    pytest.importorskip("pyinstantmeshes")
    raw = sphere(None, "head", n=200)
    key = remesh.key_of(raw, 4000)
    with pytest.raises(remesh.Cancelled):
        remesh.compute(raw, 4000, key, stopped=lambda: True)
    assert remesh.cached(key) is None
