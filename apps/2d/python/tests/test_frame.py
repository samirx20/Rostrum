"""The frame (FRAME.md): its maths match the engine's (hand-computed points), an older file's cameras become its keys
without changing a frame of the picture, a re-run script never wipes a key a person dragged, and what the document
can't hold is refused loudly."""
import math

import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, run_source
from rostrum2d.evaluate import value_at
from rostrum2d.frame import convert, view
from rostrum2d.frame.view import Shot, layer_matrix, undo, world_matrix

COMP = {"width": 1920, "height": 1080}
SAM = Who.person("sam")


def at(m, x, y):
    return (round(m[0] * x + m[2] * y + m[4], 6), round(m[1] * x + m[3] * y + m[5], 6))


def test_home_shows_every_layer_as_placed_and_a_far_layer_moves_less():
    home = Shot(960, 540, 1, 0, 960, 540)
    assert at(layer_matrix(COMP, home, {"depth": 3.0}), 123, 45) == (123, 45)
    assert at(world_matrix(COMP, home, {"depth": 3.0}), 123, 45) == (123, 45)
    # depth 1: s = 1/2, zoom 4 → 2, the frame 200 px right → 100 px for this layer.
    push = Shot(1160, 540, 4, 0, 960, 540)
    assert at(layer_matrix(COMP, push, {"depth": 1.0}), 910, 490) == (660, 440)
    # In the world view it is where the export shows it, carried back through the plain frame: F + (out − O) / zoom.
    assert at(world_matrix(COMP, push, {"depth": 1.0}), 910, 490) == (1085, 515)
    # The frame rolls 90° clockwise: a point 100 px above its centre shows 100 px left of the output centre.
    roll = Shot(1060, 540, 1, 90, 960, 540)
    assert at(layer_matrix(COMP, roll, {"depth": 0.0}), 1060, 440) == (860, 540)
    assert layer_matrix(COMP, roll, {"screenLock": True}) == (1, 0, 0, 1, 0, 0)
    # Home away from the output centre (a resized scene): at home every layer still shows as placed, shifted by O − H.
    moved_home = Shot(500, 400, 1, 0, 500, 400)
    assert at(layer_matrix(COMP, moved_home, {"depth": 2.0}), 500, 400) == (960, 540)


@pytest.mark.parametrize("depth", [0.0, 3.0, -0.5])
def test_a_drag_in_the_world_view_lands_under_the_pointer(depth):
    """Spec test 3: the frame zoomed and turned; a layer grabbed where the world view draws it moves under the pointer."""
    cam = Shot(1300, 700, 1.6, 20, 960, 540)
    w = world_matrix(COMP, cam, {"depth": depth})
    pointer = (1412.5, 377.25)
    placed = undo(w, *pointer)                               # the layer's own world px for that pointer
    assert at(w, *placed) == pytest.approx(pointer)
    # The world view agrees with the export through the plain frame: world = F + R(roll) · (out − O) / zoom.
    out = at(layer_matrix(COMP, cam, {"depth": depth}), *placed)
    r = math.radians(cam.roll)
    dx, dy = (out[0] - 960) / cam.zoom, (out[1] - 540) / cam.zoom
    assert (cam.x + math.cos(r) * dx - math.sin(r) * dy, cam.y + math.sin(r) * dx + math.cos(r) * dy) == pytest.approx(pointer)
    if depth == 0.0:
        assert placed == pytest.approx(pointer)              # depth 0 is drawn where it is placed


def _old_shot(comp, t):
    """The camera rule before frames (CAMERA.md, format 2): the later camera showing wins; none = at rest."""
    for c in reversed([l for l in comp["layers"] if l["type"] == "camera"]):
        if c.get("start", 0.0) <= t < c.get("end", 36000.0):
            return tuple(float(value_at(c, f, t)) for f in ("x", "y", "zoom", "rotation"))
    return (960.0, 540.0, 1.0, 0.0)


def test_two_cameras_become_one_frame_with_the_same_shot_at_every_frame():
    """Spec test 2 (Python side): a cut mid-move (curves and a spring), and a gap with no camera, frame by frame."""
    def k(owner, prop, t, v, ease="easeInOut", **extra):
        return {"id": f"{owner}.{prop}.k{int(t * 1000)}", "type": "key", "prop": prop, "t": t, "v": v, "ease": ease, **extra}
    a = {"id": "a", "type": "camera", "x": 960.0, "y": 540.0, "zoom": 1.0, "rotation": 0.0, "start": 0.0, "end": 1.0,
         "keys": [k("a", "x", 0.2, 800), k("a", "x", 1.6, 1400), k("a", "zoom", 0.0, 1.0, "linear"), k("a", "zoom", 2.0, 2.0)]}
    b = {"id": "b", "type": "camera", "x": 300.0, "y": 200.0, "zoom": 1.5, "rotation": 4.0, "start": 1.0, "end": 1.7,
         "keys": [k("b", "y", 0.5, 100, "spring", bounce=0.3, speed=0.5), k("b", "y", 1.5, 400)]}
    shape = {"id": "s", "type": "shape", "keys": []}
    comp = {"id": "c", "type": "comp", "width": 1920, "height": 1080, "fps": 30, "duration": 2.0, "layers": [a, shape, b]}
    old = [_old_shot(comp, n / 30) for n in range(61)]
    data, label = convert.convert({"id": "root", "type": "doc", "comps": [comp]}, KIND.lists)
    new = data["comps"][0]
    assert [l["type"] for l in new["layers"]] == ["camera", "shape"] and "cuts" in label and "a key per frame" in label
    assert not KIND.problems(data)
    for n in range(61):
        assert tuple(view.shot(new, n / 30))[:4] == pytest.approx(old[n], abs=1e-6), f"frame {n}"


def test_a_scene_without_a_camera_gets_a_still_frame_at_home():
    """Spec test 1 (Python side): the frame never leaves home, so the engine writes the page it wrote before."""
    data, label = convert.convert({"id": "root", "type": "doc", "comps": [
        {"id": "c", "type": "comp", "width": 1080, "height": 1920, "layers": [{"id": "frame", "type": "shape"}]}]}, KIND.lists)
    f = data["comps"][0]["layers"][0]
    assert (f["id"], f["x"], f["y"], f["homeX"], f["homeY"], f["keys"]) == ("c-frame", 540, 960, 540, 960, [])
    assert not view.leaves_home(f, data["comps"][0]) and "at home" in label


def test_a_script_rerun_keeps_a_frame_key_a_person_dragged():
    """Spec test 7: frame().key(...) run again never wipes the person's key."""
    src = 'comp("c", duration=3)\nframe().key("x", {0: 960, 2: 1500})\n'
    d = Document.new(KIND)
    d.run_script("s.py", run_source(src, "s.py"))
    d.apply({"op": "value.set", "target": "frame", "args": {"prop": "x", "v": 1800, "at": 2.0}}, SAM)
    d.run_script("s.py", run_source(src, "s.py"))
    assert value_at(d.item("frame"), "x", 2.0) == 1800
    assert run_source('comp("c")\ncamera("cam", x=700)\n', "old.py")["comps"][0]["layers"][0]["x"] == 700   # the old name
    with pytest.raises(RostrumError, match="cut"):
        run_source('comp("c")\ncamera("cam2", start=1)\n', "old.py")


def test_what_the_frame_refuses():
    d = Document.new(KIND)
    d.apply({"op": "comp.add", "args": {"id": "c"}}, SAM)
    for call in ({"op": "layer.remove", "target": "frame"}, {"op": "layer.add", "target": "c", "args": {"type": "camera"}},
                 {"op": "key.add", "target": "frame", "args": {"prop": "zoom", "t": 1, "v": 0}},
                 {"op": "camera.set", "target": "frame", "args": {"depth": 2}}):
        with pytest.raises(RostrumError):
            d.apply(call, SAM)
    assert [l["id"] for l in d.item("c")["layers"]] == ["frame"]
