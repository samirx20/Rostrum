"""Copies (brief 24): what agents rely on and would break silently. Making copies again with the same id is `set` (never a
second item) and never moves a held copy; the compiled node has the shape the core reads; an effector's keyed amount and
its near item's movement are baked per frame."""
import pytest
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe

SAM = Who.person()
SRC = '''
cam = camera("cam", z=3)
shot("hero", camera=cam, fps=10, start=0, end=0.5)
ground = mesh("ground", shape="plane", width=4, depth=4)
bud = mesh("bud", shape="sphere", radius=0.05, x=1, y=0.5)
ball = mesh("ball", shape="sphere", radius=0.1)
ball.key("x", {0: 0, 0.4: 2}, ease="linear")
c = copies("buds", bud, layout="grid", count=12, columns=4)
c.effector("scale", near=ball, radius=1).key("amount", {0: 0, 0.4: 1}, ease="linear")
'''


@pytest.fixture
def doc():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    return d


def node(d, id_="buds"):
    return next(n for n in describe(d.data, "hero")["items"] if n["id"] == id_)


def test_the_source_goes_inside_at_the_origin_and_the_node_has_the_cores_shape(doc):
    item = doc.item("buds")
    assert [c["id"] for c in item["children"]][0] == "bud" and doc.item("bud")["x"] == 0.0
    assert (item["x"], item["y"]) == (1.0, 0.5)                          # the copies item stands where the source stood
    n = node(doc)
    assert [c["id"] for c in n["children"]] == ["bud"]                    # effectors are not drawn children
    assert {"layout", "count", "columns", "seed", "seenBy", "seenSize"} <= set(n["props"])
    assert "held" not in n["props"] and n["held"] == [] and n["props"]["seenBy"] == ""   # not a surface: no camera test


def test_make_with_an_existing_id_acts_as_set_and_never_moves_a_held_copy(doc):
    doc.apply({"op": "copies.hold", "target": ["buds"], "args": {"copy": 3, "x": 0.7, "y": 0, "z": 0.2, "ry": 30}}, SAM)
    doc.apply({"op": "copies.make", "target": ["ball"], "args": {"id": "buds", "count": 20, "layout": "circle"}}, SAM)
    item = doc.item("buds")
    assert (item["count"], item["layout"]) == (20, "circle")
    assert [c["id"] for c in item["children"] if c["type"] == "mesh"] == ["bud"]        # ball was not taken in
    assert [i["id"] for i in doc.data["items"]].count("buds") == 1
    assert node(doc)["held"] == [{"copy": 3, "x": 0.7, "y": 0.0, "z": 0.2, "rx": 0.0, "ry": 30.0, "rz": 0.0, "s": 1.0}]
    doc.apply({"op": "copies.release", "target": ["buds"], "args": {"copy": 3}}, SAM)
    assert node(doc)["held"] == []


def test_surface_layout_sends_the_shot_camera_only_while_only_seen_is_on(doc):
    doc.apply({"op": "copies.scatter", "target": ["ball"], "args": {"id": "grass", "surface": "ground", "count": 400}}, SAM)
    props = node(doc, "grass")["props"]
    assert (props["seenBy"], props["seenSize"]) == ("cam", [1920, 1080])
    doc.apply({"op": "copies.set", "target": ["grass"], "args": {"onlySeen": False}}, SAM)
    assert node(doc, "grass")["props"]["seenBy"] == ""


def test_an_effectors_keyed_amount_and_its_near_items_movement_are_baked_per_frame(doc):
    e = node(doc)["effectors"][0]
    assert e["kind"] == "scale"
    assert e["amount"] == 0.0 and e["anim"]["amount"][0] == 0.0 and e["anim"]["amount"][4] == pytest.approx(1.0)
    assert len(e["anim"]["amount"]) == len(e["anim"]["centre"]) == 5
    assert e["anim"]["centre"][4][0] == pytest.approx(2.0)                # the ball's x at 0.4 s: the centre follows it


def test_the_checker_names_a_copies_item_with_nothing_to_copy(doc):
    with pytest.raises(Exception, match="nothing to copy"):
        doc.apply({"op": "item.remove", "target": ["bud"], "args": {}}, SAM)


def test_a_start_spread_reaches_the_fall_and_keeps_a_persons_edit_on_a_rerun():
    """Vary › Start (varyStart): only on a falling copies item; sent to the core with the seed (each copy's wait comes from
    them there); left out at 0 so every stored fall keeps its key; a script re-run never wipes the person's value."""
    from rostrum3d.sim.inputs import sim_inputs
    src = '''
cam = camera("cam", z=3)
shot("hero", camera=cam, fps=24, start=0, end=2)
bud = mesh("bud", shape="sphere", radius=0.05, y=0.5)
copies("buds", bud, layout="grid", count=12, columns=4, varyMove=0.02).simulate("falls")
'''
    d = Document.new(KIND)
    d.run_script("s.py", run_source(src, "s.py"))
    assert "varyStart" not in node(d, "buds")["props"]
    _, before = sim_inputs(d.data, "hero")
    d.apply({"op": "copies.set", "target": ["buds"], "args": {"varyStart": 0.8, "seed": 7}}, SAM)
    assert (node(d, "buds")["props"]["varyStart"], node(d, "buds")["props"]["seed"]) == (0.8, 7)
    assert sim_inputs(d.data, "hero")[1] != before                      # a new spread is a new fall
    d.run_script("s.py", run_source(src, "s.py"))
    assert (d.item("buds")["varyStart"], d.item("buds")["seed"]) == (0.8, 7)
    d.apply({"op": "copies.set", "target": ["buds"], "args": {"simulate": "off"}}, SAM)
    with pytest.raises(Exception, match="varyStart"):                  # nothing falls: a start spread means nothing
        d.apply({"op": "copies.set", "target": ["buds"], "args": {"varyStart": 1.0}}, SAM)
