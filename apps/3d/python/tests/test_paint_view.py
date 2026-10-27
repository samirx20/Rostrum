"""Paint from the view, projecting a picture, coverage (brief 21): what agents and the screen rely on. A stroke drawn
through a camera lands on each item it crosses and splits at a seam; a projected picture paints only what its camera
sees; coverage counts what the shot sees painted; a scene whose texel pictures aren't drawn yet loads once without that
paint, then with it, and the next compile finds the pictures at once. The texel pictures are made here (the engine
draws them in the app)."""
import json

import numpy as np
from rostrum_core import Document, Who
from rostrum_core.cache import CACHE

from rostrum3d import KIND, compile as C, coverage, paint_scene, paint_view
from rostrum3d.texels import Picture

SAM = Who.person()
W, H, SIZE = 64, 32, 256


def _picture(items, item_of, uv_of, w=W, h=H) -> Picture:
    """A texel picture: item_of(x, y) -> index into items (-1 none), uv_of(x, y) -> (u, v), at pixel centres."""
    x, y = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    u, v = uv_of(x, y)
    idx = item_of(x, y)
    data = np.stack([np.where(idx >= 0, u, np.nan), np.where(idx >= 0, v, np.nan), idx,
                     np.where(idx >= 0, 1.0, -1.0)], -1).astype(np.float32)
    return Picture(data, items)


def _two_items():          # left half: the case, right half: the lid; each laid over its whole canvas
    return _picture(["case", "lid"], lambda x, y: (x >= W / 2).astype(float),
                    lambda x, y: ((x % (W / 2)) / (W / 2), 1 - y / H))


def _stroke(points, size=4.0, **kw):
    return {"id": "s1", "type": "stroke", "size": size, "color": "#ff0000",
            **paint_view.view_fields({"eye": [0, 0, 1], "target": [0, 0, 0], "fov": 30, "width": W, "height": H,
                                      "frame": 0, "points": points}), **kw}


def test_a_view_stroke_lands_on_each_item_it_crosses():
    pic, s = _two_items(), _stroke([[4, 16, 1.0], [60, 16, 0.5]])
    case, lid = paint_view.lay(s, pic, "case", SIZE), paint_view.lay(s, pic, "lid", SIZE)
    assert len(case) == 1 and len(lid) == 1 and case[0]["id"] == "s1"
    scale = SIZE / (W / 2)                                            # 8 canvas px per screen px
    assert abs(case[0]["size"] - 4 * scale) < 0.5                     # the brush: screen px → canvas px
    xs = [p[0] for p in case[0]["points"]]
    assert abs(xs[0] - 4 * scale) < 2 and abs(xs[-1] - 31.5 * scale) < 6    # from where it starts to the case's edge
    assert all(abs(p[1] - SIZE / 2) < 2 for p in case[0]["points"])
    assert case[0]["points"][0][2] > lid[0]["points"][-1][2]          # pressure kept along the path
    assert "viewPoints" not in case[0] and lid[0]["points"][-1][0] < 30 * scale
    got = paint_view.landed_on({"id": "case", "paintSize": SIZE, "paints": [{"id": "p", "strokes": [s]}]},
                               lambda req: pic)
    assert got[0]["runs"] == 1 and got[0]["offPx"]["max"] < 1.0 and 0.4 < got[0]["share"] < 0.6


def test_a_view_stroke_splits_at_a_seam():
    pic = _picture(["case"], lambda x, y: np.zeros_like(x),              # the right half laid on another piece
                   lambda x, y: (np.where(x < W / 2, x / W * 0.4, 0.6 + (x - W / 2) / W * 0.4), 1 - y / H))
    laid = paint_view.lay(_stroke([[4, 16], [60, 16]]), pic, "case", SIZE)
    assert [s["id"] for s in laid] == ["s1", "s1.1"]
    assert laid[0]["points"][-1][0] < 0.21 * SIZE and laid[1]["points"][0][0] > 0.59 * SIZE


def test_a_projected_picture_paints_only_what_its_camera_sees():
    pic = _picture(["wall", "box"], lambda x, y: (x >= W / 2).astype(float),    # the box hides the wall's right half
                   lambda x, y: (x / W, 1 - y / H))
    red = np.zeros((H, W, 4), np.float32)
    red[..., 0] = red[..., 3] = 1
    size = 128                                                        # 2 texels a pixel: the holes between are filled
    out = paint_view.splat(pic, "wall", red, size)
    seen = out[4:size - 4, 4:size // 2 - 4]
    assert (seen[..., 3] > 0.99).all() and (seen[..., 0] > 0.99).all()
    assert (out[:, size // 2 + 4:, 3] == 0).all()                     # behind the box: unpainted


def test_coverage_counts_what_the_shot_sees_painted():
    alpha = np.zeros((SIZE, SIZE), np.uint8)
    alpha[:, :SIZE // 2] = 255                                        # the case's left half painted
    got = coverage.measure(_two_items(), {"case": alpha, "lid": np.zeros((SIZE, SIZE), np.uint8)})
    assert got["case"]["seen"] == W * H // 2 and abs(got["case"]["percent"] - 50) < 1
    assert got["lid"]["percent"] == 0
    tinted = coverage.tint(np.zeros((SIZE, SIZE, 3), np.float32), coverage.seen_texels(_two_items(), "case", SIZE), alpha)
    assert tinted[:, :SIZE // 2].max() == 0 and tinted[:, SIZE // 2:, 0].max() > 0.3    # only the unpainted half


def test_view_paint_waits_for_its_texel_picture_then_paints(tmp_path, monkeypatch):
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.apply([{"op": "mesh.add", "args": {"id": "case", "shape": "box"}},
             {"op": "mesh.add", "args": {"id": "lid", "shape": "box"}},
             {"op": "camera.add", "args": {"id": "cam", "z": 2}},
             {"op": "shot.add", "args": {"id": "hero", "camera": "cam", "start": 0, "end": 1}},
             *[{"op": "mesh.set", "target": [i], "args": {"paintSize": SIZE}} for i in ("case", "lid")],
             *[{"op": "paint.add", "target": [i], "args": {"id": f"{i}_p"}} for i in ("case", "lid")]], SAM)
    view = {"eye": [0, 0, 1], "target": [0, 0, 0], "fov": 30, "width": W, "height": H, "frame": 0,
            "points": [[4, 16, 1.0], [60, 16, 1.0]]}                  # as the screen gives it (tidied to view… fields)
    d.apply([{"op": "stroke.add", "target": [f"{i}_p"], "args": {"size": 4, "color": "#ff0000", "view": view}}
             for i in ("case", "lid")], SAM, label="Paint from the view")              # one drag: one undo step
    assert not KIND.check(d.data) and paint_view.view_of(d.item("lid_p")["strokes"][0])["points"] == view["points"]
    scene = C.describe(d.data, "hero")
    assert sorted(j["item"]["id"] for j in scene["paintLater"]) == ["case", "lid"]
    asked, loads = [], []

    def texels(req):                                                  # the engine, holding the first load
        asked.append(req)
        pic = _two_items()
        data = np.stack([pic.uv[..., 0], pic.uv[..., 1], pic.item, pic.distance], -1).astype("<f4")
        data.tofile(req["file"])
        return {"ok": True, "width": W, "height": H, "file": req["file"], "items": pic.items}
    paint_scene.send(scene, loads.append, texels)
    first, second = loads
    assert "paintLater" not in first and len(asked) == 1               # one picture serves both items
    mats = {m["id"]: m for m in second["materials"]}
    assert {"case__paint", "lid__paint"} <= set(mats)
    assert mats["case__paint"]["props"]["baseColorTexture"].endswith("surface.png")
    again = C.describe(d.data, "hero")                                # the picture is kept: painted at once
    assert "paintLater" not in again and "lid__paint" in [m["id"] for m in again["materials"]]
    assert json.dumps(again["materials"], sort_keys=True) == json.dumps(second["materials"], sort_keys=True)
