"""The agent paint tools' plain maths (mcp/paint_spots.py, paint_canvas.py), no engine: what breaks silently is a canvas
spot found at the wrong place on the shot's picture (canvas y is down, v is up), a hidden spot called seen, or a
stroke reported landed on the wrong items or with the wrong unit."""
import numpy as np
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source, unfold
from rostrum3d.mcp import paint_canvas as PC, paint_look, paint_spots as PS

SIZE = 1024
SAM = Who.person()


def _texel_picture():
    """A 40×20 picture: the left half shows item 0 with uv running u 0.1→0.5 left to right, v 0.9→0.7 top to bottom;
    the right half shows nothing (−1)."""
    h, w = 20, 40
    uv = np.full((h, w, 2), np.nan, np.float32)
    item = np.full((h, w), -1, np.int16)
    xs, ys = np.meshgrid(np.arange(20), np.arange(h))
    uv[:, :20, 0] = 0.1 + 0.4 * (xs + 0.5) / 20
    uv[:, :20, 1] = 0.9 - 0.2 * (ys + 0.5) / h
    item[:, :20] = 0
    return uv, item


def test_canvas_pixels_and_uv_round_trip_with_y_down():
    assert PS.px_of([0.25, 0.75], SIZE) == [256.0, 256.0]
    assert PS.uv_of([256, 256], SIZE) == [0.25, 0.75]
    assert np.allclose(PS.uv_of(PS.px_of([0.3, 0.1], SIZE), SIZE), [0.3, 0.1])


def test_a_canvas_spot_is_found_at_its_pixel_and_a_spot_off_the_item_is_not_seen():
    uv, item = _texel_picture()
    want = [0.1 + 0.4 * 12.5 / 20, 0.9 - 0.2 * 5.5 / 20]            # the uv shown at pixel (12, 5)
    r = PS.nearest_seen(uv, item == 0, want, SIZE)
    assert r["pixel"] == [12, 5] and r["seen"] and r["offPx"] < 1
    far = PS.nearest_seen(uv, item == 0, [0.9, 0.2], SIZE)          # elsewhere on the canvas: not in the picture
    assert far is not None and not far["seen"] and far["offPx"] > 100
    assert PS.nearest_seen(uv, item == 3, want, SIZE) is None       # an item not in the picture at all


def test_coverage_counts_only_seen_pixels_and_no_uv_is_unpainted():
    uv, item = _texel_picture()
    alpha = np.zeros((SIZE, SIZE), np.float32)
    alpha[:, : int(0.3 * SIZE)] = 1.0                                # painted where u < 0.3: the left half of the item
    seen, painted = PS.painted_on_screen(uv, item, {0: alpha})
    assert seen.sum() == 400 and painted[:, :10].all() and not painted[:, 10:].any()
    hatched = PS.hatch(np.zeros((20, 40, 3), np.uint8), seen & ~painted)
    assert hatched[:, :10].max() == 0 and hatched[:, 10:20].max() > 0 and hatched[:, 20:].max() == 0
    assert PS.sample(alpha, np.array([[np.nan, np.nan]]))[0] == 0


def test_stroke_lines_say_where_and_in_which_unit():
    view = PS.stroke_line({"stroke": "s3", "layer": "colour_1", "view": True, "shot": "Hero 01", "items": ["case", "lid"],
                           "landed": True, "offPx": 1.24, "verdict": "landed"})
    assert view == "stroke s3 (From the view, Hero 01, layer colour_1): landed on case and lid, at most 1.2 screen px outside the line"
    surf = PS.stroke_line({"stroke": "s1", "layer": "l", "items": ["lid"], "landed": True, "offPx": 0.4, "box": [10, 20, 90, 60], "verdict": "landed"})
    assert "canvas px off" in surf and "(canvas x 10–90, y 20–60)" in surf
    assert PS.stroke_line({"stroke": "s2", "layer": "l", "landed": False, "verdict": "missed by 5.0 px on average"}).endswith("missed by 5.0 px on average")


def test_a_mesh_stroke_is_measured_on_its_canvas_and_found_under_its_uv():
    unfold.use_unfold(lambda doc, id_, size: {"uvs": [0.25, 0.75] * 6, "charts": 1, "used": 0.5})
    d = Document.new(KIND, item="scene")
    d.run_script("lid.py", run_source('mesh("lid", shape="cylinder", radius=0.03, height=0.01)', "lid.py"))
    d.apply({"op": "mesh.unfold", "target": ["lid"]}, SAM)
    for layer, channel, pts, colour in (("under", "colour", [[20, 128, 1], [236, 128, 1]], "#ff0000"),
                                        ("top", "roughness", [[128, 40, 1], [128, 216, 1]], "#b0b0b0")):
        d.apply({"op": "paint.add", "target": ["lid"], "args": {"id": layer, "name": layer, "channel": channel}}, SAM)
        d.apply({"op": "stroke.add", "target": [layer], "args": {"id": f"s_{layer}", "points": pts, "color": colour, "size": 20}}, SAM)
    d.apply({"op": "mesh.set", "target": ["lid"], "args": {"paintSize": 256}}, SAM)
    item = d.item("lid")
    held = PC.laid(None, None, item)
    rows = paint_look._rows_surface(held, 256, item, item["paints"][1])
    assert rows[0]["stroke"] == "s_top" and rows[0]["landed"] and rows[0]["offPx"] < 2 and rows[0]["items"] == ["lid"]
    x0, y0, x1, y1 = rows[0]["box"]
    assert x0 <= 118 and x1 >= 138 and y0 <= 30 and y1 >= 226
    top = PC.top_painted(held, 256, PS.uv_of([128, 128], 256))       # where both cross: the upper layer
    assert top["layer"] == "top" and top["channel"] == "roughness"
    assert PC.top_painted(held, 256, PS.uv_of([40, 128], 256))["layer"] == "under"
    assert PC.top_painted(held, 256, PS.uv_of([40, 40], 256)) is None
