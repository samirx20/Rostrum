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


def test_brush_settings_set_without_a_screen_and_hide_when_not_sculpting():
    from rostrum_core.conditions import holds
    from rostrum3d import fields as F
    d = Document.new(KIND)
    d.apply({"op": "clay.add", "args": {"id": "head", "at": [0, 1, 0], "radius": 0.1}}, SAM)
    d.apply({"op": "clay.set", "target": ["head"], "args": {"brushSize": 0.05, "brush": "carve", "symmetry": "off"}}, SAM)
    assert d.item("head")["brushSize"] == 0.05 and d.item("head")["brush"] == "carve"       # agents: always valid
    p = F.param("clay", "brushSize")
    assert holds(p.valid_when, d.item("head"), KIND.facts(d.item("head"), d))               # no screen: the fact is on
    assert not holds(p.valid_when, d.item("head"), {**KIND.facts(d.item("head"), d), "sculpting": False})  # Select


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


def test_auto_detail_is_finer_for_a_close_up():
    from rostrum3d import clay_detail
    d = Document.new(KIND)
    d.run_script("s.py", run_source('''
blob = clay("blob")
blob.lump((0, 0, 0), 0.05)
camera("near", z=0.5)
camera("far", z=5)
camera("away", z=0.5, ry=180)
shot("close", camera="near")
shot("wide", camera="far")
''', "s.py"))
    data, blob = d.data, d.item("blob")
    both = clay_detail.detail(data, blob)
    wide = clay_detail.detail({**data, "shots": [s for s in data["shots"] if s["id"] == "wide"]}, blob)
    assert both == 0.0003 and wide == 0.0028 and both < wide          # 10 cm clay, 50 mm lens, 1920 px wide
    behind = {**data, "shots": [{**data["shots"][0], "camera": "away"}]}
    assert clay_detail.detail(behind, blob) == 0.0005                 # no shot sees it: radius / 100
    assert clay_detail.detail(data, {**blob, "detailMode": "fixed", "detail": 0.004}) == 0.004
    moved = {**data, "items": [({**i, "z": 0.501} if i["id"] == "near" else i) for i in data["items"]]}
    assert clay_detail.detail(moved, blob) == both                   # a small move: same number, same cache


def test_cl2_brush_settings_set_without_a_screen_and_go_into_the_stroke():
    d = Document.new(KIND)
    d.apply({"op": "clay.add", "args": {"id": "head", "at": [0, 1, 0], "radius": 0.1}}, SAM)
    d.apply({"op": "clay.set", "target": ["head"], "args": {"brush": "mask", "brushFalloff": 0.9, "brushSpacing": 0.1,
                                                             "frontOnly": False}}, SAM)
    d.apply({"op": "clay.set", "target": ["head"], "args": {"detailMode": "fixed", "detail": 0.003}}, SAM)
    d.apply({"op": "clay.stroke", "target": ["head"], "args": {"dabList": DABS, "invert": True}}, SAM)
    step = chain(d.item("head")["steps"])[-1]
    assert (step["op"], step["falloff"], step["spacing"], step["frontOnly"], step["invert"]) == ("mask", 0.9, 0.1,
                                                                                                False, True)
    assert d.item("head")["detail"] == 0.003


def test_cl1_dab_files_still_read(tmp_path):
    import struct
    from rostrum3d.clay_dabs import pack, unpack
    old = struct.pack("<4sI", b"CLD1", 2) + struct.pack("<18f", *[x for r in DABS for x in r])
    assert pack(DABS) == old                                           # CL1's dabs keep their file name and key
    assert [x for r in unpack(old) for x in r] == pytest.approx([x for r in DABS for x in r], abs=1e-7)
    pen = [DABS[0] + [0.5, 0.8], DABS[1]]                              # a pen: CLD2, a dab without one scales 1
    assert unpack(pack(pen))[1][9:] == [1.0, 1.0] and pack(pen)[:4] == b"CLD2"
