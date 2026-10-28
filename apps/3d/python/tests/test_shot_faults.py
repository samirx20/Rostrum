"""Faults first for a 3D shot (mcp/shot_faults.py): a near-black picture, a subject cut by the frame and a floating ball come back as
faults with stable ids, and a render is refused while they are open and let through when `keep` explains them. Synthetic: no engine."""
import pytest
from PIL import Image
from rostrum_core import Document
from rostrum_core.errors import RostrumError

from rostrum3d import KIND, run_source
from rostrum3d.compile import shot_info
from rostrum3d.mcp import shot_faults

SRC = '''
camera("cam", z=3)
mesh("ball", shape="sphere", radius=0.2, y_world=0.5)
mesh("crate", shape="box", width=0.2, height=0.2, depth=0.2, x=0.5)
shot("hero", camera="cam", fps=24, start=0, end=24)
'''


def _found(tmp_path, grey=3):
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    info = dict(shot_info(doc.data, "hero"))
    png = tmp_path / "dark.png"
    Image.new("RGB", (64, 36), (grey, grey, grey)).save(png)
    return shot_faults.check(doc.data, info, [0, 12, 24], {12: png})


def test_a_dark_picture_a_cut_subject_and_a_floating_ball_are_faults_with_stable_ids(tmp_path):
    found = _found(tmp_path)
    ids = [f["id"] for f in found]
    assert "dark:hero" in ids and "cut_edge:ball" in ids and "floating:ball" in ids, ids
    assert "floating:crate" not in ids and "cut_edge:crate" not in ids            # the crate rests on the ground, inside the picture
    assert ids == [f["id"] for f in _found(tmp_path)]                              # the same problem keeps its id on a re-run
    assert all(f["fix"] and f["what"] for f in found) and "top" in next(f for f in found if f["id"] == "cut_edge:ball")["what"]


def test_a_render_is_refused_without_keep_and_passes_when_each_fault_is_explained(tmp_path):
    found = _found(tmp_path)
    png = tmp_path / "shot.png"
    png.write_bytes(b"png")
    with pytest.raises(RostrumError) as e:
        shot_faults.deliver(found, None, "render_still", [png])
    assert "NOT DONE" in e.value.line() and not png.exists() and (tmp_path / "shot.NOT-DONE.png").exists()
    png.write_bytes(b"png")
    keep = {f["id"]: "the ball is meant to hover, cropped and dim" for f in found}
    shot_faults.deliver(found, keep, "render_still", [png])
    assert png.exists()
