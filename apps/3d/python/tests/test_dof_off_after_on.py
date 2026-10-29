"""Depth of field turned off renders sharp in an engine that rendered it on before (Drop, 2026-10-29: Cycles kept the last
camera's aperture when the f-stop went to 0, so a re-export with dof off was blurred). Needs the built engine and a GPU;
skipped without them."""
import numpy as np
import pytest
from PIL import Image
from rostrum_core import Document

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe
from rostrum3d.runtime import find_exe
from rostrum3d.start_scene import SOURCE as START

SRC = '''
for i in range(5):
    mesh(f"b{i}", shape="box", width=0.05, height=0.3, depth=0.05, x=-0.4 + 0.2 * i, material=material(f"k{i}", baseColor="#101010"))
cam = camera("cam", focalLength=50, y=0.3, z=1.5, DOF).aim((0, 0.15, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def _scene(dof: str) -> dict:
    d = Document.new(KIND)                             # the new scene's floor and lights, then the posts and camera
    d.run_script("start.py", run_source(START, "start.py"))
    d.run_script("s.py", run_source(SRC.replace("DOF", dof), "s.py", d))
    return describe(d.data, "hero")


def _render(eng, png) -> np.ndarray:
    eng.render(camera="cam", renderer="cycles", frame=0, width=240, height=135, samples=16, png=str(png))
    return np.asarray(Image.open(png).convert("L"), np.float64)


def test_dof_off_renders_the_same_after_a_render_with_it_on(tmp_path):
    if not find_exe().exists():
        pytest.skip("3D engine not built")
    from rostrum3d.engine import Engine
    on, off = _scene("dof=True, fStop=0.5, focusDistance=0.3"), _scene("dof=False")
    with Engine() as eng:
        eng.load(off)
        fresh = _render(eng, tmp_path / "fresh.png")
    with Engine() as eng:
        eng.load(on)
        blurred = _render(eng, tmp_path / "on.png")
        eng.load(off)
        after = _render(eng, tmp_path / "after.png")
    assert fresh.std() > 5, "the picture should show the posts"
    assert np.abs(blurred - fresh).mean() > 3 * np.abs(after - fresh).mean(), "the dof-on render should differ"
    assert np.abs(after - fresh).mean() < 2.0, "dof off after dof on is still blurred"
