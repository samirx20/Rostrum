"""A cloth touches itself (core cloth_self.h): a sheet draped over a box and a ball gathers on the floor without any of
its edges passing through its own triangles (round 4's Drape had 88 at rest: the judges' crumpled spiky tabs)."""
from __future__ import annotations

import json

import pytest
from rostrum_core import Document, Who
from rostrum_core.cache import CACHE

from rostrum3d import KIND, run_source
from rostrum3d.runtime import find_exe
from rostrum3d.sim.result import CLOTH_HEADER, cloth_file

np = pytest.importorskip("numpy")
cKDTree = pytest.importorskip("scipy.spatial").cKDTree

SRC = '''
cam = camera("cam", z=3, y=1)
shot("drape", camera=cam, fps=24, start=0, end=3.5)
mesh("box", shape="box", width=0.45, height=0.4, depth=0.45, x=-0.28).simulate("still")
mesh("ball", shape="sphere", radius=0.22, x=0.3, z=0.05).simulate("still")
mesh("sheet", shape="plane", width=1.5, depth=1.5, y=0.85).simulate("cloth", clothWeight=0.08, stiffness=0.15, clothAir=3)
'''


def _crossings(x, tri) -> int:
    """Edges of the sheet that pass through one of its own triangles (not one they share a point with)."""
    e = np.unique(np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1), axis=0)
    span = np.median(np.linalg.norm(x[e[:, 0]] - x[e[:, 1]], axis=1))
    near = cKDTree(x[tri].mean(1)).query_ball_point((x[e[:, 0]] + x[e[:, 1]]) / 2, 1.5 * span)
    ei = np.repeat(np.arange(len(e)), [len(p) for p in near])
    E, T = e[ei], tri[np.concatenate([np.array(p, int) for p in near])]
    keep = ~((E[:, :1] == T).any(1) | (E[:, 1:] == T).any(1))
    E, T = E[keep], T[keep]
    p0, p1, a, b, c = x[E[:, 0]], x[E[:, 1]], x[T[:, 0]], x[T[:, 1]], x[T[:, 2]]
    n = np.cross(b - a, c - a)
    d0, d1 = ((p0 - a) * n).sum(1), ((p1 - a) * n).sum(1)
    hit = d0 * d1 < 0
    q = p0 + (p1 - p0) * (d0 / np.where(hit, d0 - d1, 1))[:, None]
    s = [(np.cross(v - u, q - u) * n).sum(1) for u, v in ((a, b), (b, c), (c, a))]
    inside = ((s[0] >= 0) & (s[1] >= 0) & (s[2] >= 0)) | ((s[0] <= 0) & (s[1] <= 0) & (s[2] <= 0))
    return int((hit & inside).sum())


def test_a_draped_sheet_does_not_pass_through_itself(tmp_path, monkeypatch):
    if not find_exe().exists():
        pytest.skip("3D engine not built")
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    d.apply([{"op": "sim.run", "target": ["drape"]}], Who.person())
    res = next((tmp_path / "cache").rglob("result.json"))
    c = next(c for c in json.loads(res.read_text())["cloth"] if c["item"] == "sheet")
    raw = (res.parent / cloth_file("sheet")).read_bytes()
    P, T = c["points"], c["triangles"]
    tri = np.frombuffer(raw, np.int32, 3 * T, CLOTH_HEADER).reshape(T, 3)
    last = np.frombuffer(raw, np.float32, 3 * P, len(raw) - 12 * P).reshape(P, 3).astype(np.float64)
    assert _crossings(last, tri) == 0
