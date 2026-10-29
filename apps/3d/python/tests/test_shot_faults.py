"""Notes for a 3D shot (mcp/shot_faults.py): a near-black picture, a subject cut by the frame and a floating ball come back as
notes with stable ids, each an observation with its numbers, never a fix. Synthetic: no engine."""
from PIL import Image
from rostrum_core import Document

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


def test_a_dark_picture_a_cut_subject_and_a_floating_ball_are_notes_with_stable_ids(tmp_path):
    found = _found(tmp_path)
    ids = [f["id"] for f in found]
    assert "dark:hero" in ids and "cut_edge:ball" in ids and "floating:ball" in ids, ids
    assert "floating:crate" not in ids and "cut_edge:crate" not in ids            # the crate rests on the ground, inside the picture
    assert ids == [f["id"] for f in _found(tmp_path)]                              # the same thing keeps its id on a re-run
    by = {f["id"]: f for f in found}
    assert all(set(f) == {"id", "what", "when"} and f["what"] for f in found)     # observations: no fix, no verdict
    assert "top" in by["cut_edge:ball"]["what"] and "mean brightness 0.01" in by["dark:hero"]["what"]
    assert "m above the ground" in by["floating:ball"]["what"] and "y = " in by["floating:ball"]["what"]


def test_nothing_is_held_back_any_more():
    assert not hasattr(shot_faults, "deliver")                                     # a render ships under the asked name
