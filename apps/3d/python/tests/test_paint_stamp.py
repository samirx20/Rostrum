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


def _scattered_plane(folder, cells=40, side=0.2):
    """A clay surface file (CLS1) of a flat square facing +z, each triangle its own tiny piece of the paint picture,
    the pieces shuffled: as a real clay's unfolding is (many small pieces, nothing of the picture next to its place)."""
    import struct
    g = np.linspace(-side / 2, side / 2, cells + 1)
    x, y = np.meshgrid(g, g)
    pts = np.stack([x.ravel(), y.ravel(), np.zeros(x.size)], 1)
    k = np.arange(cells * cells)
    i, j = k // cells, k % cells
    a, b, c, d = i * (cells + 1) + j, i * (cells + 1) + j + 1, (i + 1) * (cells + 1) + j + 1, (i + 1) * (cells + 1) + j
    tris = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    m, per = len(tris), int(np.ceil(np.sqrt(len(tris))))
    slot = np.random.default_rng(3).permutation(m)
    cx, cy = (slot % per) / per, (slot // per) / per
    corner = np.array([[0.15, 0.15], [0.85, 0.15], [0.85, 0.85]]) / per
    uv = np.stack([cx, cy], 1)[:, None, :] + corner[None]
    f = folder / "surf" / "surface.cls"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"CLS1" + struct.pack("<5I", 1, 512, len(pts), m, 0) + pts.astype("<f4").tobytes()
                  + np.tile([0, 0, 1.0], (len(pts), 1)).astype("<f4").tobytes() + tris.astype("<i4").tobytes()
                  + uv.astype("<f4").tobytes())
    from rostrum3d import clay_paint
    return clay_paint.read(f)


def test_a_clay_stamp_lands_whole_however_its_surface_is_cut(tmp_path):
    """The bug it guards: on a clay laid flat in many small pieces, a stamp drawn as one dab on the flat picture kept
    only scraps of the picture (the relief showed nothing)."""
    from rostrum3d import paint_scene
    surface = _scattered_plane(tmp_path)
    d = _doc(tmp_path)
    Image.fromarray(np.full((64, 64), 255, np.uint8)).save(tmp_path / "white.png")
    d.apply({"op": "paint.stamp", "target": ["head"], "args": {"picture": "white.png", "at": [0, 0, 0, 0, 0, 1],
                                                               "size": 0.08, "depth": 1}}, SAM)
    item = {**d.item("head"), "paintSize": 512}
    held, splats, keys = paint_scene._laid({"item": item}, surface, {})
    layer = item["paints"][0]["id"]
    assert not held["paints"][0]["strokes"] and keys[layer]                 # laid as a decal, not a kit dab
    a = splats[layer][..., 3]
    mid = surface.points[surface.tris].mean(1)                             # each triangle's middle and its texel
    uv = surface.uv.mean(1)
    px = a[np.clip(((1 - uv[:, 1]) * 512).astype(int), 0, 511), np.clip((uv[:, 0] * 512).astype(int), 0, 511)]
    inside = np.abs(mid[:, :2]).max(1) < 0.036                             # under the 8 cm picture
    outside = np.abs(mid[:, :2]).max(1) > 0.045
    assert inside.sum() > 100 and (px[inside] > 0.9).all()                  # all of the picture, on every piece
    assert (px[outside] < 0.05).all()
