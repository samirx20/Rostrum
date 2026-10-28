"""Cloth (brief 26b): what the core is asked for a cloth, that its settings key the stored result, and that a stored drape
reaches the cloth's node (the core reads the file) with its place held at the first frame."""
from __future__ import annotations

import struct
from pathlib import Path

import pytest
from rostrum_core import Document, Who
from rostrum_core.cache import CACHE

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe, shot_info
from rostrum3d.sim import ops as sim_ops
from rostrum3d.sim.inputs import JOLT_VERSION, SIM_VERSION, sim_inputs
from rostrum3d.sim.result import cloth_bytes, cloth_file

SAM = Who.person()
SRC = '''
cam = camera("cam", z=4, y=0.5)
shot("drape", camera=cam, fps=10, start=0, end=2)
mesh("plinth", shape="box", width=0.4, height=0.4, depth=0.4).simulate("still")
sheet = mesh("sheet", shape="plane", width=0.8, depth=0.8, y=0.5).simulate("cloth", stiffness=0.2, pinned="back")
sheet.key("x", {0: 0.0, 0.2: 0.3})
'''


class FakeEngine:
    """Answers `simulate` like the core for cloth only: a 3-point, 1-triangle drape per cloth, its file in the core's layout."""

    def ensure_scene(self, scene):
        pass

    def simulate(self, progress=None, **req):
        frames, cloth = req["end"] - req["start"] + 1, []
        for b in req["bodies"]:
            if b["kind"] != "cloth":
                continue
            head = b"RCL1" + struct.pack("<4i", 3, 1, frames, req["start"])
            body = struct.pack("<3i", 0, 1, 2) + struct.pack("<6f", 0, 0, 1, 0, 0, 1) + struct.pack(f"<{9 * frames}f", *[0.0] * 9 * frames)
            Path(req["folder"], cloth_file(b["item"])).write_bytes(head + body)
            cloth.append({"item": b["item"], "file": "", "points": 3, "triangles": 1, "refined": True})
        Path(req["folder"], "bodies.bin").write_bytes(b"")
        return {"ok": True, "jolt": JOLT_VERSION, "sim": SIM_VERSION, "frames": [req["start"], req["end"]], "rows": 0,
                "bodies": [], "cloth": cloth, "atRest": 0, "ms": 1, "frameMs": 0.1}

    def close(self):
        pass


@pytest.fixture
def doc(tmp_path, monkeypatch):
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    sim_ops.use_engine_factory(FakeEngine)
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    yield d
    CACHE.settle()
    sim_ops.use_engine_factory(None)


def test_a_cloths_request_and_its_settings_key_the_result(doc):
    req, k = sim_inputs(doc.data, "drape")
    sheet = next(b for b in req["bodies"] if b["item"] == "sheet")
    assert sheet == {"item": "sheet", "kind": "cloth", "weight": 0.2, "stiffness": 0.2, "air": 1.0, "pinned": "back",
                     "friction": 0.6}
    for args in ({"stiffness": 0.8}, {"pinned": "left"}, {"clothWeight": 0.5}, {"clothAir": 2.0}):
        doc.apply([{"op": "sim.set", "target": ["sheet"], "args": args}], SAM)
        assert sim_inputs(doc.data, "drape")[1] != k, args
        k = sim_inputs(doc.data, "drape")[1]


def test_a_stored_drape_reaches_the_cloths_node_and_holds_its_place(doc):
    doc.apply([{"op": "sim.run", "target": ["drape"]}], SAM)
    node = next(n for n in describe(doc.data, "drape", sim="strict")["items"] if n["id"] == "sheet")
    c = node["cloth"]
    info = shot_info(doc.data, "drape")
    assert (c["start"], c["end"], c["step"], c["smooth"]) == (info["start"], info["end"], 1, 1)
    assert Path(c["file"]).stat().st_size == cloth_bytes(3, 1, info["end"] - info["start"] + 1)
    assert "x" not in node.get("anim", {}) and node["props"]["x"] == pytest.approx(0.0)    # held at the first frame



def test_turn_into_keys_on_a_cloth_only_shot_refuses_and_says_the_cloth_stays_a_simulation(doc):
    from rostrum_core.errors import RostrumError
    from rostrum3d.sim.state import state
    doc.apply([{"op": "sim.run", "target": ["drape"]}], Who.person())
    st = state(doc.data, "drape")
    assert st["state"] == "stored" and (st["falling"], st["cloth"]) == (0, 1)     # the window offers no Turn into keys
    import copy
    before = copy.deepcopy(doc.data)
    with pytest.raises(RostrumError, match="only cloth.*stays a simulation"):
        doc.apply([{"op": "sim.to_keys", "target": ["drape"]}], Who.person())
    assert doc.item("sheet")["simulate"] == "cloth" and doc.data == before      # nothing changed, no step
