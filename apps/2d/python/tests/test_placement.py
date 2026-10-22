"""Painting's one mapping (placement.py, the engine's `place`): a stroke given in composition px lands under that point
on a layer inside a moved, turned, scaled group, under a camera that pans, zooms and rolls, and tilted in 3D. Silent
breakage here puts every stroke beside the pointer."""
import pytest
from PIL import Image
from rostrum_core import Document, Who

from rostrum2d import KIND, settings
from rostrum2d.scene import describe

SAM = Who.person("sam")


def scene_doc() -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             {"op": "comp.set", "target": "film", "args": {"width": 400, "height": 300, "duration": 1, "background": "#000000"}},
             {"op": "layer.add", "target": "film", "args": {"type": "group", "id": "g"}},
             {"op": "group.set", "target": "g", "args": {"x": 200, "y": 150, "w": 150, "h": 100, "rotation": 30, "scale": 1.3}},
             {"op": "layer.add", "target": "g", "args": {"type": "shape", "id": "card"}},
             {"op": "shape.set", "target": "card", "args": {"x": 75, "y": 50, "w": 110, "h": 70, "rotation": -10,
                                                           "fill": "#0000ff", "tiltX": 25, "tiltY": -30}},
             {"op": "layer.add", "target": "film", "args": {"type": "camera", "id": "cam"}},
             {"op": "camera.set", "target": "cam", "args": {"x": 180, "y": 140, "zoom": 1.4, "rotation": 8}}], SAM)
    return d


@pytest.mark.skipif(settings.engine_exe() is None, reason="needs a built engine")
def test_a_stroke_lands_under_its_point(tmp_path):
    from rostrum2d.engine import Engine
    with Engine() as eng:
        for x, y in ((200, 150), (225, 170)):
            d = scene_doc()
            d.apply({"op": "paint.stroke", "target": "card",
                     "args": {"points": [[x, y], [x + 0.01, y]], "size": 6, "color": "#ff0000", "hardness": 1.0}}, SAM)
            eng.load(describe(d.data))
            eng.still(0.0, tmp_path / "f.png")
            img = Image.open(tmp_path / "f.png").convert("RGB")
            red = [(i % img.width + 0.5, i // img.width + 0.5) for i, (r, g, b) in enumerate(img.get_flattened_data()) if r > 200 and g < 80]
            assert red, "the stroke left no paint"
            cx, cy = sum(p[0] for p in red) / len(red), sum(p[1] for p in red) / len(red)
            assert abs(cx - x) < 1 and abs(cy - y) < 1, (cx, cy, x, y)


def test_comp_px_strokes_use_the_running_programs_engine():
    """With a host registered (the screen's canvas engine, the MCP server's project), paint.stroke in composition px
    asks that host, with the project's markers and folder, and starts no engine of its own."""
    from rostrum_core import Document, Who
    from rostrum2d import KIND, placement
    asked, marks = [], []

    def place(scene, t, ids):
        asked.append((t, ids))
        return {i: {"m": [1, 0, 100, 0, 1, 50, 0, 0, 1], "w": 200, "h": 100, "edge": ""} for i in ids}
    host = placement.Host(place, markers=lambda: marks.append(1) or {"drop": 0.5}, folder=lambda: None)
    placement.use(host)
    try:
        d = Document.new(KIND)
        sam = Who.person("sam")
        d.apply([{"op": "comp.add", "args": {"id": "film"}},
                 {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "egg"}},
                 {"op": "shape.set", "target": "egg", "args": {"w": 200, "h": 100}}], sam)
        d.apply({"op": "paint.stroke", "target": "egg", "args": {"points": [[110, 60], [150, 60]]}}, sam)
    finally:
        placement.drop(host)
    assert asked == [(0.0, ["egg"])] and marks                       # the host's engine, with the project's markers
    pts = d.item("egg")["frames"][0]["paints"][0]["strokes"][0]["points"]
    assert [p[:2] for p in pts] == [[9.5, 9.5], [49.5, 9.5]]        # own px (10, 10) / (50, 10) -> pixel centres
