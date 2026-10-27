"""Paint on clay (3d-cl4): what would break silently. A stroke kept on the surface lands on the same 3D spot after the
clay is reshaped and unfolded anew (split cleanly at a seam); a mesh's pixel strokes paint exactly as before; a scene
whose clay surface isn't made yet loads once without the paint, then with it; Height is shown as Relief. The core's
CLS1 surface files are written here by the test (the core writes them in the app)."""
import struct
from pathlib import Path

import numpy as np
import pytest
from rostrum_core import Document, Who
from rostrum_core.cache import CACHE, cache_key
from rostrum_paint import canvas

from rostrum3d import KIND, clay_paint, compile as C, paint_scene
from rostrum3d.paint_fields import CHANNELS

SAM = Who.person()
SIZE = 1024
W = 0.1                                    # the test surfaces: a 10 cm square, 20 × 20 cells, facing +Z


def _grid(z: float):
    n = 21
    xs, ys = np.meshgrid(np.linspace(0, W, n), np.linspace(0, W, n))
    pts = np.stack([xs.ravel(), ys.ravel(), np.full(n * n, z)], 1)
    tris = []
    for j in range(n - 1):
        for i in range(n - 1):
            a, b, c, d = j * n + i, j * n + i + 1, (j + 1) * n + i, (j + 1) * n + i + 1
            tris += [[a, b, d], [a, d, c]]
    return pts, np.asarray(tris)


def _one_chart(p):
    return [0.05 + p[0] / W * 0.9, 0.05 + p[1] / W * 0.9]


def _two_charts(p, left):                  # a seam down x = W/2: the right half laid upside down elsewhere
    if left:
        return [0.05 + p[0] / (W / 2) * 0.4, 0.05 + p[1] / W * 0.9]
    return [0.55 + (p[0] - W / 2) / (W / 2) * 0.4, 0.95 - p[1] / W * 0.9]


def _write(path, z, uv_of):
    pts, tris = _grid(z)
    uv = []
    for t in tris:
        left = pts[t, 0].mean() < W / 2
        uv += [c for k in t for c in (uv_of(pts[k]) if uv_of is _one_chart else _two_charts(pts[k], left))]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"CLS1" + struct.pack("<5I", 1, SIZE, len(pts), len(tris), 1))
        f.write(np.asarray(pts, "<f4").tobytes() + np.tile([0, 0, 1], (len(pts), 1)).astype("<f4").tobytes())
        f.write(np.asarray(tris, "<i4").tobytes() + np.asarray(uv, "<f4").tobytes())
        f.write(np.asarray([0, 0, 0, len(tris)], "<i4").tobytes())
    return path


STROKE = {"id": "s1", "type": "stroke", "seed": 1, "color": "#ff0000",
          "anchors": [[0.02, 0.03, 0.0, 0, 0, 1, 1.0], [0.08, 0.03, 0.0, 0, 0, 1, 0.5]], "reach": 0.004}


def test_a_stroke_stays_on_the_same_spot_after_a_reshape(tmp_path):
    before = clay_paint.Surface(_write(tmp_path / "a" / "surface.cls", 0.0, _one_chart))
    [one] = clay_paint.lay(before, STROKE)
    assert one["points"][0][:2] == pytest.approx([(0.05 + 0.2 * 0.9) * SIZE, (1 - (0.05 + 0.3 * 0.9)) * SIZE], abs=0.05)
    assert one["size"] == pytest.approx(2 * 0.004 / (W / (0.9 * SIZE)), rel=1e-3)
    assert "anchors" not in one and one["points"][-1][2] == pytest.approx(0.5)

    after = clay_paint.Surface(_write(tmp_path / "b" / "surface.cls", 0.004, None))     # raised, unfolded in two
    left, right = clay_paint.lay(after, STROKE)                                        # split at the seam
    start = _two_charts([0.02, 0.03], True)
    assert left["points"][0][:2] == pytest.approx([start[0] * SIZE, (1 - start[1]) * SIZE], abs=0.05)
    end = _two_charts([0.08, 0.03], False)
    assert right["points"][-1][:2] == pytest.approx([end[0] * SIZE, (1 - end[1]) * SIZE], abs=0.05)
    assert right["id"] == "s1.1" and left["size"] == pytest.approx(2 * 0.004 * SIZE * (0.8 / W * 0.9 / W) ** 0.5, rel=1e-3)   # px per m: by area
    seam = _two_charts([W / 2, 0.03], True)[0] * SIZE                     # each half reaches just past the cut
    assert left["points"][-1][0] > seam >= left["points"][-2][0]


def _lid(tmp_path, monkeypatch):
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.apply([{"op": "mesh.add", "args": {"id": "lid", "shape": "box"}},
             {"op": "camera.add", "args": {"id": "cam", "z": 2}},
             {"op": "shot.add", "args": {"id": "hero", "camera": "cam", "start": 0, "end": 1}},
             {"op": "mesh.set", "target": ["lid"], "args": {"uvs": [0.5, 0.5] * 36, "paintSize": 256}},
             {"op": "paint.add", "target": ["lid"], "args": {"id": "scuffs", "channel": "roughness"}},
             {"op": "stroke.add", "target": ["scuffs"], "args": {"points": [[20, 20], [200, 90]], "size": 30}}], SAM)
    return d


def test_a_meshs_pixel_strokes_paint_as_before(tmp_path, monkeypatch):
    d = _lid(tmp_path, monkeypatch)
    scene = C.describe(d.data, "hero")
    lid = d.item("lid")
    held = {"id": "lid", "paints": lid["paints"], "paintmasks": []}           # the key pictures were made under before
    key = cache_key("paint.surface", paint_scene.VERSION, [canvas.content_key(held, 256, 256)],
                    {"size": 256, "channel": "roughness", "under": ["value", [0.5]]})
    mat = next(m for m in scene["materials"] if m["id"] == "lid__paint")
    assert mat["props"]["roughnessTexture"] == str(CACHE.path("paint", key) / "surface.png")
    assert "paintLater" not in scene


def test_a_clay_waits_for_its_surface_then_paints(tmp_path, monkeypatch):
    d = _lid(tmp_path, monkeypatch)
    d.apply([{"op": "clay.add", "args": {"id": "blob", "at": [0, 0, 0], "radius": 0.1}},
             {"op": "clay.set", "target": ["blob"], "args": {"paintSize": 256}},
             {"op": "paint.add", "target": ["blob"], "args": {"id": "skin", "channel": "height"}},
             {"op": "stroke.add", "target": ["skin"], "args": {**{k: STROKE[k] for k in ("anchors", "reach")},
                                                               "color": "#ffffff"}}], SAM)
    assert not KIND.check(d.data)
    scene = C.describe(d.data, "hero")
    node = next(n for n in scene["items"] if n["id"] == "blob")
    assert "paintSize" not in node["props"] and node["paint"]["size"] == 256
    assert [j["item"]["id"] for j in scene["paintLater"]] == ["blob"]
    loads = []

    def load(s):                                         # the core: loading a painted clay writes its surface
        loads.append(s)
        if len(loads) == 1:
            _write(Path(node["paint"]["file"]), 0.0, _one_chart)
    paint_scene.send(scene, load)
    first, second = loads
    assert "paintLater" not in first and "blob__paint" not in [m["id"] for m in first["materials"]]
    painted = next(m for m in second["materials"] if m["id"] == "blob__paint")
    assert painted["props"]["bumpTexture"].endswith("surface.png")
    again = C.describe(d.data, "hero")                   # the surface is there now: painted at once
    assert "paintLater" not in again and "blob__paint" in [m["id"] for m in again["materials"]]


def test_height_is_shown_as_relief():
    assert CHANNELS["height"][0] == "Relief"
