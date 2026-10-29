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


def test_a_view_stamp_on_a_clay_lands_whole_and_upright_as_seen(tmp_path):
    """paint.stamp with viewPoint on a clay: found on the clay through its view and laid as a decal (whole, however
    the clay's surface is cut), the picture's top toward the screen's up."""
    from rostrum3d import paint_scene
    surface = _scattered_plane(tmp_path)
    d = _doc(tmp_path)
    pic = np.zeros((64, 64), np.uint8)
    pic[:32] = 255                                                          # white on top only
    Image.fromarray(pic).save(tmp_path / "top.png")
    view = {"eye": [0, 0, 1], "target": [0, 0, 0], "fov": 30, "width": 64, "height": 64}
    d.apply({"op": "paint.stamp", "target": ["head"], "args": {"picture": "top.png", "viewPoint": [32, 32],
                                                               "size": 25.6, "depth": 1, **view}}, SAM)
    item = {**d.item("head"), "paintSize": 512}
    s = item["paints"][0]["strokes"][0]
    x, y = np.meshgrid(-0.1 + 0.2 * (np.arange(64) + 0.5) / 64, 0.1 - 0.2 * (np.arange(64) + 0.5) / 64)
    spots = np.stack([x.ravel(), y.ravel(), np.zeros(x.size)], 1)          # the plane fills the view, x right, y up
    tri, bary = surface.nearest(spots, np.tile([0, 0, 1.0], (len(spots), 1)))
    uv = np.einsum("aj,ajk->ak", bary, surface.uv[tri]).reshape(64, 64, 2)
    texel = Picture(np.dstack([uv, np.zeros((64, 64)), np.ones((64, 64))]).astype(np.float32), ["head"])
    pics = {paint_view.texel_key(paint_view.req_of(paint_view.view_of(s))): texel}
    held, splats, _ = paint_scene._laid({"item": item}, surface, pics)
    a = splats[item["paints"][0]["id"]][..., 3]
    assert not held["paints"][0]["strokes"]                                 # a decal, not a dab
    mid, tuv = surface.points[surface.tris].mean(1), surface.uv.mean(1)
    px = a[np.clip(((1 - tuv[:, 1]) * 512).astype(int), 0, 511), np.clip((tuv[:, 0] * 512).astype(int), 0, 511)]
    top = (np.abs(mid[:, 0]) < 0.034) & (mid[:, 1] > 0.006) & (mid[:, 1] < 0.034)
    bottom = (np.abs(mid[:, 0]) < 0.034) & (mid[:, 1] < -0.006) & (mid[:, 1] > -0.034)
    assert top.sum() > 30 and (px[top] > 0.9).all() and (px[bottom] < 0.05).all()


def test_a_raised_area_on_a_clay_has_no_false_slopes_at_its_pieces_edges(tmp_path, monkeypatch):
    """The bug it guards: a real clay (a million triangles) was too big to have its pieces' edges bled, so in its Relief
    picture every raised texel sat next to flat grey across a piece's edge, and the render showed grain and rings
    inside a flat stamp. Every clay is bled now, however many triangles (here: the limit set below this one's)."""
    from rostrum3d import paint_bleed, paint_scene
    monkeypatch.setattr(paint_bleed, "MOST_FACES", 100)
    surface = _scattered_plane(tmp_path)
    d = _doc(tmp_path)
    Image.fromarray(np.full((64, 64), 255, np.uint8)).save(tmp_path / "white.png")
    d.apply({"op": "paint.stamp", "target": ["head"], "args": {"picture": "white.png", "at": [0, 0, 0, 0, 0, 1],
                                                               "size": 0.08, "depth": 1}}, SAM)
    item = {**d.item("head"), "paintSize": 512}
    held, splats, keys = paint_scene._laid({"item": item}, surface, {})
    pieces = paint_bleed.pieces(item, surface, 512)
    assert pieces is not None
    png = paint_scene._picture(held, "height", held["paints"], 512, ("value", [0.5]), surface.key, None, splats,
                               {"projected": keys, "bleed": paint_bleed.key(item, surface, 512)}, pieces)
    rel = np.asarray(Image.open(png))
    raised = pieces & (rel == 255)
    assert raised.sum() > 100
    for shift in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        assert not (raised & (np.roll(rel, shift, (0, 1)) == 128)).any()   # no flat texel right next to a raised one


def test_a_clay_stamps_edge_is_an_even_slope_over_about_a_texel_and_its_middle_flat(tmp_path):
    """The bug it guards: read hard at a clay's ~1 mm texels, a stamp's edge was a one-texel step each tiny piece cut
    its own way (a speckled bevel in Final). The picture is read softened by ~SOFT texels: a slope, the plateau flat."""
    from rostrum3d import stamp_decal
    from rostrum3d.uv_raster import Geo, raster
    surface = _scattered_plane(tmp_path, cells=80)
    d = _doc(tmp_path)
    Image.fromarray(np.full((64, 64), 255, np.uint8)).save(tmp_path / "white.png")
    d.apply({"op": "paint.stamp", "target": ["head"], "args": {"picture": "white.png", "at": [0, 0, 0, 0, 0, 1],
                                                               "size": 0.08, "depth": 1}}, SAM)
    a = stamp_decal.layer_rgba(surface, d.item("head")["paints"][0]["strokes"], 512)[..., 3]
    tri, bary = raster(Geo.of_surface(surface), 512)
    on = tri >= 0
    spot = np.einsum("aj,ajk->ak", bary[on], surface.points[surface.tris[tri[on]]])
    out = np.abs(spot[:, :2]).max(1) - 0.04                                # how far outside the 8 cm square (m)
    texel = float(np.median(surface.mpp))
    v = a[on]
    assert (v[out < -3 * texel] > 0.99).all()                              # the plateau: flat
    assert (v[out > 3 * texel] < 0.01).all()
    assert 0.05 < v[(out > 0.4 * texel) & (out < 0.8 * texel)].mean() < 0.5   # a slope reaching past the edge
