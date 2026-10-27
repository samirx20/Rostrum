"""Turn into keys on a falling copies item (keyed copies, copy_keys.py): one undo step, every copy's keys are its stored
fall, the core gets them as each held copy's `anim`, and a nudge survives a re-run. The core is test_sim's stand-in."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.cache import CACHE

from rostrum3d import KIND, run_source
from rostrum3d import copy_keys as CK
from rostrum3d.compile import describe
from rostrum3d.sim import ops as sim_ops
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
    for c in range(3):                                      # the stand-in drops 0.1 m and turns 10° a frame
        assert [k["v"] for k in keyed[c]["y"]] == pytest.approx([1.0 - 0.1 * i for i in range(10)])
        assert [k["v"] for k in keyed[c]["ry"]] == pytest.approx([10.0 * i for i in range(10)])

    node = next(n for n in describe(doc.data, "drop")["items"] if n["id"] == "buds")
    assert "sim" not in node and node["held"][1]["anim"]["y"][:3] == pytest.approx([1.0, 0.9, 0.8])
    assert "s" not in node["held"][1]                       # not held: the layout keeps its size

    doc.undo(SAM)
    assert doc.item("buds")["simulate"] == "falls" and not doc.item("buds").get(CK.KEYS)     # one undo step
    doc.redo(SAM)
    doc.apply([{"op": "copies.key", "target": ["buds"], "args": {"copy": 2, "prop": "y", "t": 0.5, "v": 0.123}}], SAM)
    doc.apply([{"op": "sim.to_keys", "target": ["drop"]}, {"op": "sim.run", "target": ["drop"]}], SAM)    # a re-run
    y = {k["t"]: k["v"] for k in CK.keys_map(doc.item("buds"))[2]["y"]}
    assert y[0.5] == pytest.approx(0.123) and y[0.4] == pytest.approx(0.6)
