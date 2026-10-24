"""Bone chains (brief 19): what breaks silently is a chain lost on undo or save, or a skin whose numbers bend the mesh
the wrong way (the core trusts them)."""
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe

SAM = Who.person()
SRC = '''
strap = mesh("strap", shape="capsule", radius=0.05, height=1.2, y=0.6)
cam = camera("cam", z=3, y=0.6)
shot("s", camera=cam, fps=2, start=0, end=1.5)
'''
POINTS = [[0, 0, 0], [0, 0.4, 0], [0, 0.8, 0], [0, 1.2, 0]]         # world, up the strap


def _doc(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("t.py", run_source(SRC, "t.py"))
    d.apply({"op": "bone.chain", "target": ["strap"], "args": {"points": POINTS}}, SAM)
    return d


def _chain(data):
    strap = next(i for i in data["items"] if i["id"] == "strap")
    out, bones = [], strap["bones"]
    while bones:
        out.append(bones[0]["id"])
        bones = bones[0]["bones"]
    return out


def test_chain_is_one_step_and_saves(tmp_path):
    d = _doc(tmp_path)
    assert _chain(d.data) == ["strap_bone1", "strap_bone2", "strap_bone3"] and d.item("strap")["skinned"]
    assert d.item("strap_bone1")["y"] == -0.6 and d.item("strap_bone3")["length"] == 0.4   # mesh space: strap at y 0.6
    d.undo(SAM)
    assert _chain(d.data) == []
    d.redo(SAM)
    d.apply({"op": "key.add", "target": ["strap_bone2"], "args": {"prop": "rz", "t": 1.0, "v": 90}}, SAM)
    d.save()
    again = Document.open(tmp_path, "scene", KIND)
    assert _chain(again.data) == _chain(d.data) and again.item("strap_bone2")["keys"][0]["v"] == 90


def test_skin_bends_the_tail_round_the_middle_joint(tmp_path):
    d = _doc(tmp_path)
    for t, v in ((0.0, 0.0), (1.0, 90.0)):
        d.apply({"op": "key.add", "target": ["strap_bone2"], "args": {"prop": "rz", "t": t, "v": v, "ease": "linear"}}, SAM)
    skin = next(i for i in describe(d.data, "s")["items"] if i["id"] == "strap")["skin"]
    assert skin["rest"][2] == [0.0, 0.2, 0.0, 0.0, 0.6, 0.0] and len(skin["pose"]) == 3     # frames 0, 1, 2
    m = skin["pose"][2][2]                                     # frame 2 (1 s): bone 3, bent 90° round Z at y −0.2
    tail = [sum(m[r * 3 + c] * p for c, p in enumerate([0.0, 0.6, 0.0])) + m[9 + r] for r in range(3)]
    assert all(abs(a - b) < 1e-6 for a, b in zip(tail, [-0.8, -0.2, 0.0]))
    assert skin["pose"][0][2][:9] == [1, 0, 0, 0, 1, 0, 0, 0, 1]                              # frame 0: at rest
