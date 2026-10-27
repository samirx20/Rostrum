"""Texel pictures (brief 21): what painting from the view and coverage rely on and would break silently. The engine's
file is read pixel for pixel (rows top first, u v item distance); a picture's key ignores materials and paint, so
repainting never asks the engine again, but moving a shape does. The engine's file is written here by the test."""
import json

import numpy as np
from rostrum_core.cache import Cache

from rostrum3d import texels

W, H = 4, 3


def _write(path, items=("case", "lid")):
    data = np.full((H, W, 4), [np.nan, np.nan, -1, -1], np.float32)
    data[0, 1] = [0.25, 0.75, 1, 2.5]          # top row, second pixel: the lid at (0.25, 0.75), 2.5 m away
    data[2, 3] = [np.nan, np.nan, 0, 4.0]      # bottom right: the case, no st there
    data.astype("<f4").tofile(path)
    return {"ok": True, "width": W, "height": H, "file": str(path), "items": list(items)}


def test_read_lays_pixels_out_top_row_first(tmp_path):
    pic = texels.read(_write(tmp_path / "t.bin"))
    assert pic.uv.shape == (H, W, 2) and pic.item.dtype == np.int16
    assert pic.uv[0, 1].tolist() == [0.25, 0.75] and pic.distance[0, 1] == 2.5
    assert pic.of("lid").sum() == 1 and pic.of("lid")[0, 1]
    assert pic.of("case")[2, 3] and np.isnan(pic.uv[2, 3]).all()
    assert not pic.of("plinth").any() and pic.item[1, 1] == -1 and pic.distance[1, 1] == -1


def test_key_ignores_looks_and_cache_asks_once(tmp_path, monkeypatch):
    monkeypatch.setattr(texels, "CACHE", Cache(tmp_path / "cache"))
    scene = {"items": [{"id": "lid", "props": {"x": 0, "material": "red"}}], "materials": [{"id": "red"}]}
    repainted = {"items": [{"id": "lid", "props": {"x": 0, "material": "lid_paint"}}],
                 "materials": [{"id": "lid_paint", "baseColorTexture": "p.png"}], texels.LATER: [{"item": "lid"}]}
    moved = json.loads(json.dumps(scene))
    moved["items"][0]["props"]["x"] = 0.1
    assert texels.geometry_key(scene) == texels.geometry_key(repainted) != texels.geometry_key(moved)

    asked = []

    def ask(req):
        asked.append(req)
        return _write(req["file"])

    req = {"camera": "cam", "frame": 0, "width": W, "height": H}
    assert texels.cached(scene, req) is None                         # not kept, nothing to ask
    first = texels.cached(scene, req, ask)
    again = texels.cached(repainted, req, ask)
    assert len(asked) == 1 and again.items == first.items == ["case", "lid"]
    assert again.uv[0, 1].tolist() == [0.25, 0.75]
