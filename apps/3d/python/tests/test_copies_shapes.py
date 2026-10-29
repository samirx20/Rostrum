"""Copies field shapes and paths (PR3): what agents rely on and would break silently. A path layout sends its outline's
contours in the copies item's own space; an effector from before field shapes reads as the sphere it was; a path that
can't be run along is refused loudly."""
import pytest
from rostrum_core import Document, Who

from rostrum3d import KIND, outline, run_source
from rostrum3d.compile import describe

SAM = Who.person()
SRC = '''
cam = camera("cam", z=3)
shot("hero", camera=cam, fps=10, start=0, end=0.3)
ground = mesh("ground", shape="plane", width=4, depth=4)
word = mesh("word", shape="text", text="OI", x=2, y=0.25)
bud = mesh("bud", shape="sphere", radius=0.02, x=1, y_world=0.5)
ball = mesh("ball", shape="sphere", radius=0.1)
c = copies("buds", bud, layout="path", path=word, count=30)
c.effector("scale", near=ball, radius=1)
'''


@pytest.fixture
def doc():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    return d


def node(d, id_="buds"):
    return next(n for n in describe(d.data, "hero")["items"] if n["id"] == id_)


def test_a_path_sends_every_contour_in_the_copies_items_space(doc):
    props = node(doc)["props"]
    shapes = outline.for_item(doc.item("word"))
    want = [c for s in shapes for c in (s["outer"], *s["holes"])]           # "OI": the O's outer and hole, the I
    assert len(props["pathPoints"]) == len(want) == 3 and props["pathClosed"] == [True] * 3
    word, buds = doc.item("word"), doc.item("buds")
    dx, dy = word["x"] - buds["x"], word["y"] - buds["y"]                   # neither is turned or scaled
    for got, ref in zip(props["pathPoints"], want):
        assert len(got) == len(ref)
        assert got[0] == pytest.approx([ref[0][0] + dx, ref[0][1] + dy, 0.0], abs=1e-6)
    assert (props["path"], props["alongPath"], props["pathShift"]) == ("word", True, 0.0)


def test_an_older_effector_reads_as_a_sphere_and_a_plane_sends_its_near_items_up(doc):
    eff = next(c for c in doc.item("buds")["children"] if c["type"] == "effector")
    eff.pop("field", None)                                                  # a file from before field shapes
    eff.pop("seed", None)
    e = node(doc)["effectors"][0]
    assert not {"field", "seed", "normal"} & set(e)                         # the scene older cores read, unchanged
    doc.apply({"op": "effector.add", "target": ["buds"], "args": {"id": eff["id"], "field": "plane"}}, SAM)
    e = node(doc)["effectors"][0]
    assert e["field"] == "plane" and e["normal"] == pytest.approx([0.0, 1.0, 0.0]) and "seed" not in e
    doc.apply({"op": "effector.add", "target": ["buds"], "args": {"id": eff["id"], "field": "noise", "seed": 7}}, SAM)
    e = node(doc)["effectors"][0]
    assert (e["field"], e["seed"]) == ("noise", 7) and "normal" not in e


def test_a_path_that_is_no_outline_or_inside_the_copies_is_refused(doc):
    with pytest.raises(Exception, match="a plane mesh; a path is a text, svg or path2d mesh"):
        doc.apply({"op": "copies.make", "target": ["ball"], "args": {"layout": "path", "path": "ground"}}, SAM)
    with pytest.raises(Exception, match="can't run along itself or along what it copies"):
        doc.apply({"op": "copies.set", "target": ["buds"], "args": {"path": "bud"}}, SAM)
    assert node(doc)["props"]["path"] == "word"                              # refused: nothing changed
    with pytest.raises(Exception, match="path names no item"):              # an agent's make names its path
        doc.apply({"op": "copies.make", "target": ["ball"], "args": {"layout": "path"}}, SAM)
    doc.apply({"op": "copies.set", "target": ["buds"], "args": {"path": ""}}, SAM)    # the screen: Layout first, then Path
    props = node(doc)["props"]
    assert props["visible"] is False and "pathPoints" not in props                    # nothing drawn until a path is picked
