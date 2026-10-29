"""Stamping a picture as relief (paint.stamp): one stroke of one whole-picture dab, on the Relief layer it makes when
the item has none, all one undo step; a picture file is kept in the project padded (brightness = height), so the whole
picture, corners too, lies inside the round dab at the size asked; turn 0 from the view stands it as the screen's up."""
import numpy as np
from PIL import Image
from rostrum_core import Document, Who
from rostrum_paint import canvas

from rostrum3d import KIND, paint_view, run_source, unfold
from rostrum3d.texels import Picture

SAM = Who.person()
SRC = '''
mesh("lid", shape="cylinder", radius=0.03, height=0.01)
clay("head", radius=0.1)
'''


def _doc(tmp_path):
    unfold.use_unfold(lambda doc, id_, size: {"uvs": [0.25, 0.75] * 6, "charts": 1, "used": 0.5})
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("s.py", run_source(SRC, "s.py"))
    return d


def test_a_stamp_is_one_stroke_and_one_undo_step(tmp_path):
    d = _doc(tmp_path)
    d.apply({"op": "paint.stamp", "target": ["head"], "args": {"picture": "sponge", "at": [0, 0.2, 0, 0, 1, 0],
                                                               "size": 0.04, "depth": -0.6, "turn": 30}}, SAM)
    (layer,) = d.item("head")["paints"]
    assert layer["channel"] == "height" and layer["name"] == "Relief 1"
    (s,) = layer["strokes"]
    assert s["anchors"] == [[0, 0.2, 0, 0, 1, 0, 1.0]] and s["reach"] == 0.02
    assert (s["texture"], s["stampTurn"], s["follow"], s["color"], s["opacity"]) == ("sponge", 30, False, "#000000", 0.6)
    d.apply({"op": "paint.stamp", "target": ["head"], "args": {"picture": "sponge", "at": [0, 0.2, 0, 0, 1, 0],
                                                               "size": 0.02}}, SAM)
    assert [len(p["strokes"]) for p in d.item("head")["paints"]] == [2]       # the same Relief layer
    d.undo(SAM)
    d.undo(SAM)
    assert d.item("head").get("paints", []) == []                              # the layer goes with its first stamp
    assert not KIND.check(d.data)


def test_a_picture_file_is_kept_as_a_relief_tip(tmp_path):
    d = _doc(tmp_path)
    pic = np.zeros((64, 64), np.uint8)
    pic[16:48, 16:48] = 255                                                    # a white square on black: raise it
    Image.fromarray(pic).save(tmp_path / "square.png")
    d.apply({"op": "paint.stamp", "target": ["lid"], "args": {"picture": "square.png", "point": [512, 512],
                                                              "size": 200, "depth": 1}}, SAM)
    s = d.item("lid")["paints"][0]["strokes"][0]
    assert s["texture"].startswith("brushtip_") and s["points"] == [[512, 512, 1.0]]
    layer = np.zeros((1024, 1024, 4), np.float32)                              # the one dab lays the whole square
    canvas.stamp(layer, s, 1024, 1024, {})
    a = layer[..., 3]
    assert a[512, 512] > 0.95 and a[512 - 90, 512 - 90] < 0.05 and a[512 - 40, 512 + 40] > 0.95


def _laid_alpha(tmp_path, pic):
    d = _doc(tmp_path)
    Image.fromarray(pic).save(tmp_path / "pic.png")
    d.apply({"op": "paint.stamp", "target": ["lid"], "args": {"picture": "pic.png", "point": [512, 512], "size": 200,
                                                              "depth": 1}}, SAM)
    s = d.item("lid")["paints"][0]["strokes"][0]
    layer = np.zeros((1024, 1024, 4), np.float32)
    canvas.stamp(layer, s, 1024, 1024, {})
    return layer[..., 3]


def test_the_whole_picture_corners_too_lies_inside_the_dab_at_its_size(tmp_path):
    a = _laid_alpha(tmp_path, np.full((48, 64), 255, np.uint8))     # all white, wider than tall: 200 x 150 px
    assert min(a[512 - 72, 512 - 97], a[512 + 72, 512 + 97], a[512 - 72, 512 + 97], a[512 + 72, 512 - 97]) > 0.9
    assert max(a[512, 512 + 108], a[512 + 82, 512], a[512 - 82, 512]) < 0.05    # nothing past the picture's edges


def test_turn_0_from_the_view_is_the_screens_up(tmp_path):
    d = _doc(tmp_path)
    view = {"eye": [0, 0, 1], "target": [0, 0, 0], "fov": 30, "width": 64, "height": 32}
    for turn in (0, 30):
        d.apply({"op": "paint.stamp", "target": ["lid"], "args": {"picture": "sponge", "viewPoint": [32, 16],
                                                                  "size": 8, "turn": turn, **view}}, SAM)
    a, b = d.item("lid")["paints"][0]["strokes"]
    x, y = np.meshgrid(np.arange(64) + 0.5, np.arange(32) + 0.5)

    def flat(u, v):                     # a flat mesh facing the camera, its paint picture laid as given
        return Picture(np.stack([u, v, np.zeros_like(u), np.ones_like(u)], -1).astype(np.float32), ["lid"])
    upright = flat(x / 64, 1 - y / 32)                                  # canvas up = screen up
    turned = flat(y / 32, x / 64)                                       # canvas +x = screen down: screen up is −x
    assert paint_view.lay(a, upright, "lid", 256)[0]["angle"] == 0
    assert paint_view.lay(b, upright, "lid", 256)[0]["angle"] == 30
    assert paint_view.lay(a, turned, "lid", 256)[0]["angle"] == -90    # the picture's up (sin a, −cos a) = −x
