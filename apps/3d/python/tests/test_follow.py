"""Follow and stick (brief 18): what breaks silently is a bud that jumps when it is let go, one that doesn't ride
the lid's hinge, or a constraint lost on undo or save."""
from rostrum_core import Document, Who

from rostrum3d import KIND, aim, run_source
from rostrum3d.compile import _Frames

SAM = Who.person()
FPS = 24
SRC = '''
lid = mesh("lid", shape="box", width=0.6, height=0.05, depth=0.4, y_world=0.5, pz=-0.2, z=-0.2)
lid.key("rx", {0.5: 0, 2.0: -100}, ease="linear")
bud = mesh("bud", shape="sphere", radius=0.05, y_world=0.575)
floor = mesh("floor", shape="plane", width=4, depth=4)
cam = camera("cam", z=3)
shot("s", camera=cam, fps=24, start=0, end=3)
'''


def _doc(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("t.py", run_source(SRC, "t.py"))
    d.apply({"op": "follow.add", "target": ["bud"], "args": {"item": "lid", "until": 1.4}}, SAM)   # one step
    return d


def _where(data, id_, f, at=(0.0, 0.0, 0.0)):
    return aim.point(_Frames(data, range(0, 3 * FPS), FPS).world(id_, f), list(at))


def test_bud_rides_the_hinged_lid_then_lets_go_without_a_jump(tmp_path):
    d = _doc(tmp_path)
    hinge = [_where(d.data, "lid", f, (0, 0, -0.2)) for f in (0, 30, 60)]       # the lid's back edge
    assert all(abs(a - b) < 1e-9 for h in hinge for a, b in zip(h, [0, 0.5, -0.2]))   # turns around its hinge pivot
    still, rode = _where(d.data, "bud", 10), _where(d.data, "bud", 33)
    assert abs(still[1] - 0.575) < 1e-9 and rode[1] > 0.6               # rides up as the lid opens around its hinge
    go = round(1.4 * FPS)
    before, after, later = (_where(d.data, "bud", f) for f in (go - 1, go, go + 12))
    assert after == later                                               # let go: it stays where it was let go
    assert sum((a - b) ** 2 for a, b in zip(before, after)) ** 0.5 < 0.05   # no jump: one frame's ride at most


def test_follow_and_stick_undo_and_save(tmp_path):
    d = _doc(tmp_path)
    d.apply({"op": "mesh.set", "target": ["floor"], "args": {"y": 0}}, SAM)
    d.apply({"op": "stick.add", "target": ["lid"], "args": {"item": "floor", "height": 0.25}}, SAM)
    assert abs(_where(d.data, "lid", 0)[1] - 0.25) < 1e-9               # stands 0.25 above the floor
    d.undo(SAM)
    assert "stick" not in d.item("lid") or not d.item("lid")["stick"]
    d.redo(SAM)
    d.save()
    again = Document.open(tmp_path, "scene", KIND)
    assert again.item("bud")["follow"] == "lid" and again.item("lid")["stick"] == "floor"
    assert _where(again.data, "bud", 40) == _where(d.data, "bud", 40)


def test_the_gizmo_stands_where_a_followed_or_stuck_item_is_seen(tmp_path):
    """18b: the seen placement (resolve.Frames.carrier) carries the item's own x y z to where it is drawn, and a
    change to its own offset moves it there by exactly the carrier's step, so a gizmo drag lands under the pointer."""
    from rostrum3d.resolve import seen
    d = _doc(tmp_path)
    d.apply({"op": "mesh.set", "target": ["floor"], "args": {"y": 0.1}}, SAM)
    d.apply({"op": "stick.add", "target": ["lid"], "args": {"item": "floor", "height": 0.3}}, SAM)
    for id_, f in (("bud", 33), ("lid", 20)):
        own = {k: d.item(id_).get(k, 0.0) for k in ("x", "y", "z")}
        m = seen(d.data, id_, f, FPS)
        here = aim.point(m, [own["x"], own["y"], own["z"]])
        pivot = [d.item(id_).get(k, 0.0) for k in ("px", "py", "pz")]
        assert all(abs(a - b) < 1e-9 for a, b in zip(here, _where(d.data, id_, f, pivot))), id_
        d.apply({"op": "mesh.set", "target": [id_], "args": {"x": own["x"] + 0.1}}, SAM)
        moved = _where(d.data, id_, f, pivot)
        step = aim.point(m, [own["x"] + 0.1, own["y"], own["z"]])
        assert all(abs(a - b) < 1e-6 for a, b in zip(step, moved)), id_
