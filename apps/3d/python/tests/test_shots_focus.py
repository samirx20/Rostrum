"""Two things that would break silently (SPEC §8): a new shot from a view is one undo step (camera and shot together),
and a camera focusing on an item keeps it sharp while it moves (focus distance follows it every frame)."""
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe

SAM = Who.person()
SRC = '''
logo = mesh("logo", shape="box", z=-2)
logo.key("z", {0: -2, 1: -4})
cam = camera("cam", dof=True, focusItem="logo")
shot("hero", name="Hero 01", camera=cam, fps=24, start=0, end=1, width=1280, height=720)
'''


def doc():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    return d


def test_shot_from_view_is_one_undo_step():
    d = doc()
    d.apply({"op": "shot.from_view", "args": {"id": "s2", "cameraId": "c2", "position": [1, 2, 3], "turn": [-10, 20, 0],
                                              "focalLength": 85}}, SAM)
    shot, cam = d.item("s2"), d.item("c2")
    assert (shot["name"], shot["camera"], shot["width"], shot["fps"], shot["end"]) == ("Shot 2", "c2", 1280, 24, 1)
    assert (cam["x"], cam["ry"], cam["focalLength"]) == (1, 20, 85)
    d.undo(SAM)
    assert not d.has("s2") and not d.has("c2")


def test_focus_on_an_item_follows_it():
    cam = next(i for i in describe(doc().data, "hero")["items"] if i["id"] == "cam")
    assert "focusItem" not in cam["props"]
    assert cam["props"]["focusDistance"] == 2.0
    assert cam["anim"]["focusDistance"][0] == 2.0 and 3.8 < cam["anim"]["focusDistance"][-1] < 4.0
