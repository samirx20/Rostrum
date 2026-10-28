"""Simulation (brief 25 + 26a): what renders and agents rely on and would break silently. A stale result is never rendered
(sim="strict" refuses it, the render paths compute first); the same inputs give the same key and a changed input (a still
thing moved, a mass, a key on a falling thing) a new one, a colour not; the core's quaternions come back as the same turn;
Turn into keys never undoes a hand nudge when run again. The core is a stand-in writing bodies.bin as documented."""
import array
from pathlib import Path

import pytest
from rostrum_core import Document, Who
from rostrum_core.cache import CACHE

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe
from rostrum3d.sim import ops as sim_ops
from rostrum3d.sim.compute import SimError, ready
from rostrum3d.sim.inputs import JOLT_VERSION, SIM_VERSION, sim_inputs
from rostrum3d.sim.result import euler_quat, quat_euler
from rostrum3d.sim.state import state

SAM = Who.person()
SRC = '''
cam = camera("cam", z=4, y=0.5)
shot("drop", camera=cam, fps=10, start=0, end=1)
mat = material("red", baseColor="#ff0000")
bowl = mesh("bowl", shape="box", width=1, height=0.1, depth=1, material=mat).simulate("still")
bud = mesh("bud", shape="sphere", radius=0.05, y=1).simulate("falls", bounce=0.4)
'''


class FakeEngine:
    """Answers `simulate` like the core: each falling row drops 0.1 m a frame and turns 10° a frame round Y."""
    calls = 0

    def ensure_scene(self, scene):
        self.scene = scene

    def simulate(self, progress=None, **req):
        FakeEngine.calls += 1
        nodes = {n["id"]: n for n in self.scene["items"]}
        bodies = []
        for b in req["bodies"]:
            if b["kind"] == "falls":
                n = nodes[b["item"]]
                count = n["props"]["count"] if n["type"] == "copies" else 1
                bodies += [{"item": b["item"], "copy": c, "row": len(bodies) + c} for c in range(count)][:count]
        frames = range(req["start"], req["end"] + 1)
        data = array.array("f")
        for i, f in enumerate(frames):
            if progress:
                progress(i + 1, len(frames), {"frame": f})
            for _ in bodies:
                data.extend([0.0, 1.0 - 0.1 * i, 0.0, *euler_quat(0.0, 10.0 * i, 0.0)])
        Path(req["folder"], "bodies.bin").write_bytes(data.tobytes())
        return {"ok": True, "jolt": JOLT_VERSION, "sim": SIM_VERSION, "frames": [req["start"], req["end"]], "rows": len(bodies),
                "file": str(Path(req["folder"], "bodies.bin")), "bodies": bodies, "atRest": len(bodies), "ms": 1}

    def close(self):
        pass


@pytest.fixture
def doc(tmp_path, monkeypatch):
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    sim_ops.use_engine_factory(FakeEngine)
    FakeEngine.calls = 0
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    yield d
    CACHE.settle()
    sim_ops.use_engine_factory(None)


def key(d):
    return sim_inputs(d.data, "drop")[1]


def bud(scene):
    return next(n for n in scene["items"] if n["id"] == "bud")


def test_same_inputs_same_key_and_each_real_change_a_new_one(doc):
    k = key(doc)
    assert key(doc) == k
    doc.apply([{"op": "material.set", "target": ["red"], "args": {"baseColor": "#00ff00"}}], SAM)
    assert key(doc) == k                                             # a colour never changes the result
    for call in ({"op": "mesh.set", "target": ["bowl"], "args": {"x": 0.2}},                    # move the bowl
                 {"op": "sim.set", "target": ["bud"], "args": {"massFromSize": False, "mass": 2.0}},
                 {"op": "key.add", "target": ["bud"], "args": {"prop": "x", "t": 0.0, "v": 0.0}},
                 {"op": "key.add", "target": ["bud"], "args": {"prop": "x", "t": 0.5, "v": 1.0}}):
        doc.apply([call], SAM)
        assert key(doc) != k, call
        k = key(doc)


def test_a_stale_result_is_never_rendered(doc):
    with pytest.raises(SimError, match="not computed"):
        describe(doc.data, "drop", sim="strict")
    doc.apply([{"op": "sim.run", "target": ["drop"]}], SAM)
    assert FakeEngine.calls == 1 and state(doc.data, "drop")["state"] == "stored"
    assert bud(describe(doc.data, "drop", sim="strict"))["anim"]["y"][:3] == pytest.approx([1.0, 0.9, 0.8])
    doc.apply([{"op": "mesh.set", "target": ["bowl"], "args": {"y": -0.5}}], SAM)                # move the bowl
    assert state(doc.data, "drop")["state"] == "out of date"
    assert bud(describe(doc.data, "drop"))["anim"]["y"][1] == pytest.approx(0.9)                # the viewport keeps the old one
    with pytest.raises(SimError, match="out of date"):
        describe(doc.data, "drop", sim="strict")
    scene = ready(doc.data, "drop", engine_factory=FakeEngine)                                  # the render paths: compute first
    assert FakeEngine.calls == 2 and "anim" in bud(scene)


def test_the_cores_quaternion_is_the_same_turn():
    for turn in [(10, 20, 30), (-75, 40, 170), (90, 0, 0), (0, 89, -45)]:
        back = quat_euler(euler_quat(*turn))
        a, b = euler_quat(*turn), euler_quat(*back)
        assert abs(sum(x * y for x, y in zip(a, b))) == pytest.approx(1.0, abs=1e-9)          # same rotation (q or -q)
        if abs(turn[1]) < 89.9:
            assert back == pytest.approx(turn, abs=1e-6)


def test_on_2s_holds_and_turn_into_keys_keeps_a_nudge(doc):
    doc.apply([{"op": "sim.set", "target": ["drop"], "args": {"simTiming": "2s"}}], SAM)
    doc.apply([{"op": "sim.run", "target": ["drop"]}], SAM)
    y = bud(describe(doc.data, "drop"))["anim"]["y"]
    assert y[:4] == pytest.approx([1.0, 1.0, 0.8, 0.8])
    doc.apply([{"op": "sim.to_keys", "target": ["drop"]}], SAM)
    item = doc.item("bud")
    assert item["simulate"] == "off" and {k["ease"] for k in item["keys"]} == {"hold"}
    ys = sorted((k["t"], k["v"]) for k in item["keys"] if k["prop"] == "y")
    assert [t for t, _ in ys] == pytest.approx([0.0, 0.2, 0.4, 0.6, 0.8])
    nudged = next(k for k in item["keys"] if k["prop"] == "y" and k["t"] == pytest.approx(0.8))
    doc.apply([{"op": "key.set", "target": [nudged["id"]], "args": {"v": 0.123}}], SAM)          # a person's nudge
    doc.apply([{"op": "sim.to_keys", "target": ["drop"]}, {"op": "sim.run", "target": ["drop"]}], SAM)   # a re-run
    assert doc.item(nudged["id"])["v"] == pytest.approx(0.123)


def test_a_result_a_render_computed_is_adopted_as_the_shots_stored_one(doc):
    from rostrum3d.sim.state import adoptable
    doc.apply([{"op": "sim.run", "target": ["drop"]}], SAM)
    assert not adoptable(state(doc.data, "drop"))                          # up to date and recorded: nothing to do
    doc.apply([{"op": "mesh.set", "target": ["bowl"], "args": {"y": -0.5}}], SAM)
    assert not adoptable(state(doc.data, "drop"))                          # out of date: nothing to adopt yet
    ready(doc.data, "drop", engine_factory=FakeEngine)                     # the render computes it
    st = state(doc.data, "drop")
    assert st["state"] == "stored" and adoptable(st)
    doc.apply([{"op": "sim.run", "target": ["drop"]}], SAM)                # what the window does then (SimJob.adopt)
    assert FakeEngine.calls == 2 and not adoptable(state(doc.data, "drop"))
    assert bud(describe(doc.data, "drop"))["anim"]["y"][1] == pytest.approx(0.9)


def test_the_view_shows_the_fall_the_render_computed_for_falling_copies(tmp_path, monkeypatch):
    """The render path's key and result are the ones state() and the viewport's overlay read (a falling copies item,
    a still ground moved after an earlier result: the 3D sweep's 'render vs view' case)."""
    from rostrum3d.sim.compute import compute
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    sim_ops.use_engine_factory(FakeEngine)
    FakeEngine.calls = 0
    try:
        d = Document.new(KIND)
        d.run_script("s.py", run_source('''
cam = camera("cam", z=4, y=0.5)
shot("drop", camera=cam, fps=10, start=0, end=3)
mesh("ground", simulate="still", shape="plane", width=6, depth=6)
bud = mesh("bud", shape="sphere", radius=0.03, x=-0.5, y=0.6)
copies("buds", source=bud, layout="line", count=12, spacingX=0.09, simulate="falls")
''', "s.py"))
        older = compute(d.data, "drop", engine_factory=FakeEngine)           # a result in the store the shot never recorded
        d.apply([{"op": "mesh.set", "target": ["ground"], "args": {"y": 0.1}}], SAM)
        assert state(d.data, "drop")["state"] == "not computed"
        rendered = ready(d.data, "drop", engine_factory=FakeEngine)           # what render.still draws
        st = state(d.data, "drop")
        assert st["state"] == "stored" and st["key"] != older and st["key"] == sim_inputs(d.data, "drop")[1]
        buds = lambda scene: next(n for n in scene["items"] if n["id"] == "buds")["sim"]   # noqa: E731
        assert buds(describe(d.data, "drop")) == buds(rendered)            # before the window adopts it
        d.apply([{"op": "sim.run", "target": ["drop"]}], SAM)                 # SimJob.adopt
        assert FakeEngine.calls == 2 and buds(describe(d.data, "drop")) == buds(rendered)
        assert st["key"] in buds(rendered)["file"]
    finally:
        CACHE.settle()
        sim_ops.use_engine_factory(None)
