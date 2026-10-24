"""The world picture (camera spec § 8.4, test 4): inside the frame's outline the canvas shows exactly the export, and
around it the world, drawn where the world view places it. Silent breakage here makes the outline lie."""
import sys

import numpy as np
import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, settings
from rostrum2d.scene import describe

SAM = Who.person("sam")
needs_engine = pytest.mark.skipif(settings.engine_missing_reason() is not None or sys.platform != "win32",
                                  reason=settings.engine_missing_reason() or "the engine's pixels are Windows only")


def scene_doc(frame: dict) -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "width": 400, "height": 300, "duration": 1, "background": "#102040"}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "near"}},
             {"op": "shape.set", "target": "near", "args": {"x": 220, "y": 160, "w": 120, "h": 80, "fill": "#ff8000"}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "far"}},
             {"op": "shape.set", "target": "far", "args": {"x": 150, "y": 120, "w": 90, "h": 90, "fill": "#20e040", "depth": 2}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "away"}},
             {"op": "shape.set", "target": "away", "args": {"x": 900, "y": 150, "w": 100, "h": 100, "fill": "#ff00ff"}},
             {"op": "camera.set", "target": "frame", "args": frame}], SAM)
    return d


def rgba(got) -> np.ndarray:
    view, w, h, stride = got
    try:
        return np.frombuffer(view, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).astype(int).copy()
    finally:
        view.release()


@needs_engine
def test_inside_the_outline_is_the_export_and_the_world_goes_on_around_it():
    from rostrum2d.engine import Engine
    z = 1.25
    with Engine() as eng:
        eng.load(describe(scene_doc({"x": 260, "y": 180, "zoom": z, "rotation": 0}).data))
        export = rgba(eng.pixels(0.0))
        # The frame's top-left in the world is F − O / z = (100, 60); 10 device px of world round it, at the frame's size.
        world = rgba(eng.pixels(0.0, world={"x": 100 - 10 / z, "y": 60 - 10 / z, "w": 1000, "h": 300, "scale": z}))
        assert [[round(v, 3) for v in p] for p in eng.quad] == [[100, 60], [420, 60], [420, 300], [100, 300]]
        inside = world[10:10 + 300, 10:10 + 400]
        assert np.abs(inside - export).max() <= 1          # the export, pixel for pixel (the output step's dither)
        # The layer far outside the frame is drawn in the world, where it is placed (depth 0): magenta round (900, 150).
        px = world[int((150 - 60) * z) + 10, int((900 - 100) * z) + 10]
        assert px[0] > 200 and px[1] < 60 and px[2] > 200, px


@needs_engine
def test_a_frame_at_home_draws_the_world_in_one_pass_and_the_frame_is_the_export():
    from rostrum2d.engine import Engine
    with Engine() as eng:
        eng.load(describe(scene_doc({}).data))
        export = rgba(eng.pixels(0.0))
        world = rgba(eng.pixels(0.0, world={"x": -50, "y": -20, "w": 1100, "h": 400, "scale": 1}))
        assert np.abs(world[20:320, 50:450] - export).max() <= 1
        assert world[170, 950, 0] > 200 and world[170, 950, 1] < 60        # the layer outside the frame, as placed
        assert (rgba(eng.pixels(0.0)) == export).all()      # the export after a world picture: byte for byte (the stage clips again)
