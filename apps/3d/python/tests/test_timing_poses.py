"""Stepped timing and poses (brief 17): what breaks silently is a timing or pose lost on undo or save, values that
don't actually hold for n frames, a smooth camera that steps with them, or a pose that takes more than one undo."""
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe

SAM = Who.person()
SRC = '''
bud = mesh("bud", shape="sphere", radius=0.1)
bud.key("y", {0: 0, 1: 1}, ease="linear")
cam = camera("cam", z=3)
cam.key("x", {0: 0, 1: 1}, ease="linear")
shot("s", camera=cam, fps=12, start=0, end=1)
'''


def _doc(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("t.py", run_source(SRC, "t.py"))
    return d


def _anim(data, id_, prop):
    return next(n for n in describe(data, "s")["items"] if n["id"] == id_)["anim"][prop]


def test_stepped_timing_holds_undoes_and_saves(tmp_path):
    d = _doc(tmp_path)
    smooth = _anim(d.data, "bud", "y")
    d.apply({"op": "mesh.set", "target": ["bud"], "args": {"timing": "on2"}}, SAM)
    y, cx = _anim(d.data, "bud", "y"), _anim(d.data, "cam", "x")
    assert all(y[i] == y[i + 1] == smooth[i] for i in range(0, len(y) - 1, 2))      # each value held 2 frames
    assert len(set(cx)) == len(cx)                                                  # the camera stays smooth
    d.undo(SAM)
    assert _anim(d.data, "bud", "y") == smooth
    d.redo(SAM)
    d.save()
    again = Document.open(tmp_path, "scene", KIND)
    assert again.item("bud")["timing"] == "on2" and _anim(again.data, "bud", "y") == y


def test_pose_save_apply_one_step_each_and_saved(tmp_path):
    d = _doc(tmp_path)
    d.apply({"op": "pose.save", "target": ["bud"], "args": {"id": "up", "name": "Up", "at": 1.0}}, SAM)
    pose = d.item("up")
    assert dict(zip(pose["fields"], pose["values"]))["bud.y"] == 1.0
    d.apply({"op": "pose.apply", "target": ["up"], "args": {"at": 0.5}}, SAM)
    keys = {k["t"]: k["v"] for k in d.item("bud")["keys"] if k["prop"] == "y"}
    assert keys[0.5] == 1.0
    d.undo(SAM)                                                                     # the apply: one step
    assert 0.5 not in {k["t"] for k in d.item("bud")["keys"] if k["prop"] == "y"}
    d.apply({"op": "pose.apply", "target": ["up"], "args": {"at": 0.5, "share": 0.25}}, SAM)   # a breakdown
    assert {k["t"]: k["v"] for k in d.item("bud")["keys"] if k["prop"] == "y"}[0.5] == 0.25
    d.undo(SAM)
    d.undo(SAM)                                                                     # the save: one step
    assert not d.data.get("poses")
    d.redo(SAM)
    d.save()
    assert Document.open(tmp_path, "scene", KIND).item("up")["name"] == "Up"
