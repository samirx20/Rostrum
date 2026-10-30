"""A sewn seam holds shut to its last pair under the garment's weight (core/src/cloth_sew.cpp). Two panels sewn along their
top edges hang over a bar, like a shirt's shoulders: each seam end is a free corner the panel's weight pulls on. A change
to how seams pull (sim versions 17-19 were all tried on the shirt's neck ends) must keep this shut. Runs the real engine's
cloth; skipped without it."""
from __future__ import annotations

import math
import struct
from pathlib import Path

import pytest
from rostrum_core import Document
from rostrum_core.cache import CACHE

from rostrum3d import KIND, garment, run_source
from rostrum3d.runtime import find_exe
from rostrum3d.sim import inputs as SI
from rostrum3d.sim.compute import compute
from rostrum3d.sim.result import cloth_file

SRC = '''
cam = camera("cam", z=2, y=0.8)
shot("hang", camera=cam, fps=24, start=0, end=2)
mesh("bar", shape="capsule", radius=0.02, height=0.8, rz=90, y_world=0.88).simulate("still")
panel = [[-0.15, 0], [0.15, 0], [0.15, 0.3], [-0.15, 0.3]]
garment("flap", clothWeight=0.15, stiffness=0.25, sewTime=0.5, pieces=[
    {"name": "front", "outline": panel, "at": [0, 0.6, 0.04]},
    {"name": "back", "outline": panel, "at": [0, 0.6, -0.04], "turn": 180}],
  seams=[{"a": ["front", 2], "b": ["back", 2]}])
'''


def _last_frame(path: Path):
    b = path.read_bytes()                                  # sim/result.py's RCL1 layout
    points, tris, frames, _ = struct.unpack_from("<4i", b, 4)
    at = 20 + tris * 12 + points * 8 + (frames - 1) * points * 12
    return [struct.unpack_from("<3f", b, at + 12 * i) for i in range(points)]


def test_a_seam_over_a_bar_stays_shut_to_its_ends(tmp_path, monkeypatch):
    if not find_exe().exists():
        pytest.skip("3D engine not built")
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    made = garment.make(next(i for i in doc.data["items"] if i["id"] == "flap"))
    key = compute(doc.data, "hang", tmp_path)
    pts = _last_frame(Path(CACHE.get(SI.KIND, key)) / cloth_file("flap"))
    stored = {}                                            # the stored points: the pattern's, in first use by a triangle
    for p in (i for t in made["triangles"] for i in t):
        stored.setdefault(p, len(stored))
    gaps = {(a, b): math.dist(pts[stored[a]], pts[stored[b]]) for a, b in made["seams"]}
    ends = [tuple(made["seams"][0]), tuple(made["seams"][-1])]
    assert max(gaps[e] for e in ends) <= 0.001, f"seam ends {[round(gaps[e] * 1000, 1) for e in ends]} mm apart"
    assert max(gaps.values()) <= 0.001, f"widest pair {max(gaps.values()) * 1000:.1f} mm"
    assert min(p[1] for p in pts) > 0.3, "the flap fell off the bar"
    CACHE.settle()
