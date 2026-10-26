"""Clay: what would break silently. A script re-run keeps the strokes a person sculpted, in order; a stroke is one
undo step; a step's key (what the core compares to know what it holds) stays the same for the same steps, and
saving inline dabs into a file changes no key."""
import pytest
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.clay_dabs import read
from rostrum3d.clay_scene import chain

SAM = Who.person()
SRC = '''
head = clay("head", y=1.6)
head.lump((0, 0, 0), 0.1).lump((0, -0.02, 0.09), 0.03, name="nose")
'''
DABS = [[0.0, 0.02, 0.1, 0.0, 0.2, 0.98, 0.0, 0.0, 0.0], [0.01, 0.02, 0.1, 0.1, 0.2, 0.97, 0.0, 0.0, 0.0]]


def steps(d):
    return [(s["id"], s["step"]) for s in d.item("head")["steps"]]


def test_rerun_keeps_a_persons_strokes_in_order():
    d = Document.new(KIND)
    d.run_script("head.py", run_source(SRC, "head.py"))
    d.apply({"op": "clay.stroke", "target": ["head"], "args": {"dabList": DABS}}, SAM)
    mine = d.item("head")["steps"][-1]["id"]
    d.run_script("head.py", run_source(SRC, "head.py"))                          # the same script again
    assert steps(d) == [("head.s1", "piece"), ("head.s2", "piece"), (mine, "stroke")]
    changed = SRC.replace("0.03, name", "0.04, name") + 'head.lump((0, 0.05, 0), 0.05, name="hair")\n'
    d.run_script("head.py", run_source(changed, "head.py"))                      # changed, one more piece
    assert d.item("head.s2")["radius"] == 0.04
    assert [i for i, _ in steps(d)].count(mine) == 1
    order = [i for i, _ in steps(d)]
    assert order.index("head.s1") < order.index("head.s2") < order.index(mine)   # still after what it sculpted on
    assert set(order) == {"head.s1", "head.s2", "head.s3", mine}


def test_a_stroke_is_one_undo_step():
    d = Document.new(KIND)
    d.apply({"op": "clay.add", "args": {"id": "head", "at": [0, 1, 0], "radius": 0.1}}, SAM)
    before = steps(d)
    d.apply({"op": "clay.stroke", "target": ["head"], "args": {"dabList": DABS, "brush": "carve"}}, SAM)
    assert len(steps(d)) == len(before) + 1
    d.undo(SAM)
    assert steps(d) == before


def test_step_keys_are_stable(tmp_path):
    inline = Document.new(KIND)                                 # no folder: the dabs stay in the document
    filed = Document.new(KIND, folder=tmp_path, item="scene")   # a folder: they go into clay/<hash>.dabs
    for d in (inline, filed):
        d.apply({"op": "clay.add", "args": {"id": "head", "at": [0, 1, 0], "radius": 0.1}}, SAM)
        d.apply({"op": "clay.stroke", "target": ["head"], "args": {"dabList": DABS}}, SAM)
    a, b = inline.item("head")["steps"][-1], filed.item("head")["steps"][-1]
    assert a["dabList"] and b["dabs"].startswith("clay/") and not b.get("dabList")
    assert [x for r in read(tmp_path, b["dabs"]) for x in r] == pytest.approx([x for r in DABS for x in r], abs=1e-7)
    keys = [s["key"] for s in chain(inline.item("head")["steps"])]
    assert keys == [s["key"] for s in chain(filed.item("head")["steps"])]       # the file ref keys as the inline dabs
    assert keys == [s["key"] for s in chain(inline.item("head")["steps"])]      # same steps, same keys
    assert len(set(keys)) == 2                                                  # each step its own key
