"""Turn into keys on a falling copies item (keyed copies, copy_keys.py): one undo step, every copy's keys are its stored
fall, the core gets them as each held copy's `anim`, and a nudge survives a re-run. The core is test_sim's stand-in.
The keys are thinned (sim/thin.py): few keys, and they replay every simulated frame within the tolerance."""
import array
import math
from pathlib import Path

import pytest
from rostrum_core import Document, Who
from rostrum_core.cache import CACHE

from rostrum3d import KIND, run_source
from rostrum3d import copy_keys as CK
from rostrum3d.compile import describe
from rostrum3d.sim import ops as sim_ops
from rostrum3d.sim.result import euler_quat, trs
from rostrum3d.sim.thin import TOL
from test_sim import FakeEngine

SAM = Who.person()
SRC = '''
cam = camera("cam", z=4, y=0.5)
shot("drop", camera=cam, fps=10, start=0, end=1)
bowl = mesh("bowl", shape="box", width=1, height=0.1, depth=1).simulate("still")
bud = mesh("bud", shape="sphere", radius=0.05, y=1)
copies("buds", bud, layout="line", count=3).simulate("falls")
'''


@pytest.fixture
def doc(tmp_path, monkeypatch):
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    sim_ops.use_engine_factory(FakeEngine)
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    yield d
    CACHE.settle()
    sim_ops.use_engine_factory(None)


def test_copies_become_keyed_in_one_step_and_keep_a_nudge(doc):
    doc.apply([{"op": "sim.run", "target": ["drop"]}], SAM)
    doc.apply([{"op": "sim.to_keys", "target": ["drop"]}], SAM)
    buds = doc.item("buds")
    assert buds["simulate"] == "off"
    keyed = CK.keys_map(buds)
    assert sorted(keyed) == [0, 1, 2]
    for c in range(3):                                      # the stand-in drops 0.1 m and turns 10° a frame: a line
        assert [(k["t"], k["v"]) for k in keyed[c]["y"]] == pytest.approx([(0.0, 1.0), (0.9, 0.1)])
        assert [k["v"] for k in keyed[c]["ry"]] == pytest.approx([0.0, 90.0])
        assert [k["v"] for k in keyed[c]["x"]] == pytest.approx([keyed[c]["x"][0]["v"]] * 2)   # still: two keys

    node = next(n for n in describe(doc.data, "drop")["items"] if n["id"] == "buds")
    assert "sim" not in node and node["held"][1]["anim"]["y"][:3] == pytest.approx([1.0, 0.9, 0.8])
    assert "s" not in node["held"][1]                       # not held: the layout keeps its size

    doc.undo(SAM)
    assert doc.item("buds")["simulate"] == "falls" and not doc.item("buds").get(CK.KEYS)     # one undo step
    doc.redo(SAM)
    doc.apply([{"op": "copies.key", "target": ["buds"], "args": {"copy": 2, "prop": "y", "t": 0.5, "v": 0.123}}], SAM)
    doc.apply([{"op": "sim.to_keys", "target": ["drop"]}, {"op": "sim.run", "target": ["drop"]}], SAM)    # a re-run
    y = {k["t"]: k["v"] for k in CK.keys_map(doc.item("buds"))[2]["y"]}
    assert y == pytest.approx({0.0: 1.0, 0.5: 0.123, 0.9: 0.1})


def _fall(f: int, c: int, fps: int) -> tuple[list[float], tuple]:
    """Copy c at frame f: dropped from 1 m, bouncing on the floor with half its speed back, turning ever faster."""
    t, y, v, g = f / fps, 1.0 + 0.2 * c, 0.0, 9.81
    for _ in range(6):                                       # up to six bounces, each found in closed form
        hit = (v + math.sqrt(v * v + 2 * g * y)) / g
        if t <= hit:
            return [0.1 * c, y + v * t - 0.5 * g * t * t, 0.0], euler_quat(0.0, 40.0 * t * t, 5.0 * t)
        t, y, v = t - hit, 0.0, 0.5 * (g * hit - v)
    return [0.1 * c, 0.0, 0.0], euler_quat(0.0, 40.0 * (f / fps) ** 2, 5.0 * f / fps)


class Bouncing(FakeEngine):
    """The stand-in with a real-looking fall: arcs, bounces, a turn that speeds up."""

    def simulate(self, progress=None, **req):
        out = super().simulate(None, **req)
        data = array.array("f")
        for i in range(req["end"] - req["start"] + 1):
            for b in out["bodies"]:
                p, q = _fall(i, b["copy"], self.fps)
                data.extend([*p, *q])
        Path(out["file"]).write_bytes(data.tobytes())
        return out


def test_thinned_keys_replay_the_fall_within_the_tolerance(tmp_path, monkeypatch):
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    Bouncing.fps = 30
    sim_ops.use_engine_factory(Bouncing)
    try:
        d = Document.new(KIND)
        d.run_script("s.py", run_source(SRC.replace("fps=10, start=0, end=1", "fps=30, start=0, end=4"), "s.py"))
        d.apply([{"op": "sim.run", "target": ["drop"]}, {"op": "sim.to_keys", "target": ["drop"]}], SAM)
        buds = d.item("buds")
        node = next(n for n in describe(d.data, "drop")["items"] if n["id"] == "buds")
    finally:
        CACHE.settle()
        sim_ops.use_engine_factory(None)
    frames = range(0, 120)
    assert len(buds[CK.KEYS]) < 0.2 * 3 * 6 * len(frames)          # far fewer than one key per frame (2,160 rows)
    anim = {h["copy"]: h["anim"] for h in node["held"]}
    for c in range(3):
        every = trs([_fall(f, c, 30) for f in frames])            # what one key per frame gave
        for prop, vals in every.items():
            for f in frames:
                assert anim[c][prop][f] == pytest.approx(vals[f], abs=TOL[prop] + 1e-5), (c, prop, f)
