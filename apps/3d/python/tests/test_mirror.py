"""Mirrored copies (3D simplicity SPEC §1 at 3:40): what breaks silently is a copy that lands on the wrong side, stops
following its original after an edit, takes an edit sent to it without passing it on, or stays behind when its
original or its clay is deleted."""
from rostrum_core import Document, Who

from rostrum3d import KIND, aim, run_source
from rostrum3d.compile import _Frames, describe

SAM = Who.person()
SRC = '''
buddy = clay("buddy", x=0.3, ry=30, symmetry="x")
buddy.lump((0, 0.1, 0), 0.1)
eye = mesh("eye", shape="sphere", radius=0.01).place_on("buddy", at=(0.36, 0.15, 0.0), normal=(0, 0, 1))
nose = mesh("nose", shape="sphere", radius=0.01).place_on(buddy, at=(0.35, 0.12, 0.0866), normal=(0, 0, 1))   # on the mirror
cam = camera("cam", z=1)
shot("s", camera=cam, fps=24, start=0, end=1)
'''


def _doc(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("t.py", run_source(SRC, "t.py"))
    return d


def _at(data, id_):
    return aim.point(_Frames(data, range(0, 1), 24).world(id_, 0), [0.0, 0.0, 0.0])


def _in_clay(data, p):
    return aim.point(aim.invert(_Frames(data, range(0, 1), 24).world("buddy", 0)), p)


def _mirrored(d):
    a, b = _in_clay(d.data, _at(d.data, "eye")), _in_clay(d.data, _at(d.data, "eye_mirrored"))
    return all(abs(x - y) < 1e-6 for x, y in zip(a, [-b[0], b[1], b[2]])) and abs(a[0]) > 0.01


def test_a_part_on_a_mirrored_clay_gets_its_copy_across_the_clays_own_mirror(tmp_path):
    d = _doc(tmp_path)
    assert d.item("eye_mirrored")["name"] == "eye (mirrored)"
    assert not d.has("nose_mirrored")                                   # on the middle: no copy
    assert _mirrored(d)                                                 # the clay is moved and turned: its own X = 0
    scene = describe(d.data, "s")
    copy = next(n for n in scene["items"] if n["id"] == "eye_mirrored")
    assert copy["props"]["shape"] == "sphere" and "mirror" not in copy["props"] and copy["props"]["sx"] > 0


def test_the_copy_follows_and_its_edits_go_to_the_original_in_one_step(tmp_path):
    d = _doc(tmp_path)
    d.apply({"op": "mesh.set", "target": ["eye"], "args": {"radius": 0.02, "y": 0.18}}, SAM)
    assert _Frames(d.data, range(0, 1), 24).values("eye_mirrored", 0)["radius"] == 0.02 and _mirrored(d)
    d.apply({"op": "mesh.set", "target": ["eye_mirrored"], "args": {"radius": 0.03}}, SAM)
    assert d.item("eye")["radius"] == 0.03                              # a size sent to the copy is the original's
    before = _in_clay(d.data, _at(d.data, "eye"))
    copy = _in_clay(d.data, _at(d.data, "eye_mirrored"))
    world = aim.point(_Frames(d.data, range(0, 1), 24).world("buddy", 0), [copy[0] - 0.02, copy[1], copy[2]])
    d.apply({"op": "mesh.set", "target": ["eye_mirrored"], "args": dict(zip("xyz", world))}, SAM)
    after = _in_clay(d.data, _at(d.data, "eye"))
    assert abs(after[0] - (before[0] + 0.02)) < 1e-5 and _mirrored(d)   # moved the other way, still mirrored
    d.undo(SAM)
    d.undo(SAM)
    assert d.item("eye")["radius"] == 0.02 and _in_clay(d.data, _at(d.data, "eye")) == before   # each one undo step


def test_deleting_the_original_or_the_clay_deletes_the_copy(tmp_path):
    d = _doc(tmp_path)
    d.apply({"op": "item.remove", "target": ["eye"]}, SAM)
    assert not d.has("eye_mirrored")
    d.undo(SAM)
    assert d.has("eye_mirrored")
    d.apply({"op": "item.remove", "target": ["buddy"]}, SAM)
    assert not d.has("eye_mirrored") and d.has("eye")


def test_material_and_paint_aimed_at_the_copy_go_to_the_original(tmp_path):
    d = _doc(tmp_path)
    d.apply({"op": "material.add", "args": {"id": "black", "baseColor": "#101010"}}, SAM)
    d.apply({"op": "material.assign", "target": ["eye_mirrored"], "args": {"material": "black"}}, SAM)
    assert d.item("eye")["material"] == "black" and d.item("eye_mirrored")["material"] == ""
    d.apply({"op": "material.from", "args": {"start": "clay", "to": ["eye_mirrored"]}}, SAM)
    assert d.item("eye")["material"] not in ("", "black") and d.item("eye_mirrored")["material"] == ""
    copy = describe(d.data, "s")["items"]
    assert len({n["props"]["material"] for n in copy if n["id"] in ("eye", "eye_mirrored")}) == 1   # both show it


def test_what_only_the_copy_would_hold_is_refused_naming_the_original(tmp_path):
    import pytest
    from rostrum_core.errors import RostrumError
    d = _doc(tmp_path)
    for call in ({"op": "key.add", "target": ["eye_mirrored"], "args": {"prop": "x", "t": 0, "v": 0.02}},
                 {"op": "item.aim", "target": ["eye_mirrored"], "args": {"point": [0, 0, 1]}}):
        with pytest.raises(RostrumError, match="mirrored copy of eye: change eye instead"):
            d.apply(call, SAM)
    assert not d.item("eye_mirrored")["keys"] and d.item("eye_mirrored")["aim"] == "none"
