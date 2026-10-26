"""Painting's one mapping (placement.py, the engine's `place`): a stroke given in composition px lands under that point
on a layer inside a moved, turned, scaled group, under a frame that pans, zooms and rolls, and tilted in 3D. Silent
breakage here puts every stroke beside the pointer."""
import pytest
from PIL import Image
from rostrum_core import Document, Who

from rostrum2d import KIND, settings
from rostrum2d.scene import describe

SAM = Who.person("sam")


def scene_doc() -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "width": 400, "height": 300, "duration": 1, "background": "#000000"}},
             {"op": "layer.add", "target": "film", "args": {"type": "group", "id": "g"}},
             {"op": "group.set", "target": "g", "args": {"x": 200, "y": 150, "w": 150, "h": 100, "rotation": 30, "scale": 1.3}},
             {"op": "layer.add", "target": "g", "args": {"type": "shape", "id": "card"}},
             {"op": "shape.set", "target": "card", "args": {"x": 75, "y": 50, "w": 110, "h": 70, "rotation": -10,
                                                           "fill": "#0000ff", "tiltX": 25, "tiltY": -30}},
             {"op": "camera.set", "target": "frame", "args": {"x": 180, "y": 140, "zoom": 1.4, "rotation": 8}}], SAM)
    return d


@pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")
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


def test_ordering_by_place_asks_the_engine_once_for_layers_that_start_at_scale_0():
    """layer.stagger's spatial orders (placement.centres_at): 48 dots scaled up from 0 are placed in ONE ask, as the
    layers sit (a layer at scale 0 is not drawn, and used to be waited for a tenth of a second at a time: ~20 s)."""
    from rostrum2d import placement
    asked, seen = [], []

    def place(scene, t, ids):
        asked.append(ids)
        seen.append({n["id"]: n for n in scene["comp"]["layers"]})
        return {i: {"m": [1, 0, 10, 0, 1, 20, 0, 0, 1], "w": 40, "h": 40, "edge": ""} for i in ids}
    d = Document.new(KIND)
    ids = [f"d{i}" for i in range(48)]
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             *[{"op": "layer.add", "target": "film", "args": {"type": "shape", "id": i}} for i in ids],
             *[{"op": "key.add", "target": i, "args": {"prop": "scale", "t": 0, "v": 0}} for i in ids]], SAM)
    placement.use(placement.Host(place))
    try:
        got = placement.centres_at(d.data, {i: 0.0 for i in ids})
    finally:
        placement.use(None)
    assert len(asked) == 1 and len(got) == 48 and got["d3"] == (30.0, 40.0)
    assert all(n["props"]["scale"] == 1.0 and "scale" not in n.get("anim", {}) for i, n in seen[0].items() if i != "frame")
