"""Stamping a picture as relief (paint.stamp): one stroke of one whole-picture dab, on the Relief layer it makes when
the item has none, all one undo step; a picture file is kept in the project as a relief tip (brightness = height)."""
import numpy as np
from PIL import Image
from rostrum_core import Document, Who
from rostrum_paint import canvas

from rostrum3d import KIND, run_source, unfold

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
    assert (s["texture"], s["angle"], s["follow"], s["color"], s["opacity"]) == ("sponge", 30, False, "#000000", 0.6)
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
