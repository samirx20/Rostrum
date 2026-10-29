"""Sculpt layers (PR4): what would break silently. A clay without layers keys exactly as before (no rebuilt cache);
a layer's strokes come after the Base at its Amount, and Amount 0 leaves the clay as without them; changing a layer's
Amount never changes the Base's keys (only the layer's own steps are redone); removing a layer takes its strokes;
baking keeps the shape and the order."""
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.clay_scene import chain

SAM = Who.person()
DABS = [[0.0, 0.02, 0.1, 0.0, 0.2, 0.98, 0.0, 0.0, 0.0], [0.01, 0.02, 0.1, 0.1, 0.2, 0.97, 0.0, 0.0, 0.0]]
SRC = '''
head = clay("head", y=1.6)
head.lump((0, 0, 0), 0.1)
head.layer("smile", amount=0.5).stroke(dabList=%r, strength=0.8)
head.layer(None).stroke(dabList=%r, brush="carve")
''' % (DABS, DABS)


def made(d):
    clay = d.item("head")
    return chain(clay["steps"], d.data, clay)


def test_a_clay_without_layers_keys_as_before():
    d = Document.new(KIND)
    d.apply({"op": "clay.add", "args": {"id": "head", "at": [0, 1, 0], "radius": 0.1}}, SAM)
    d.apply({"op": "clay.stroke", "target": ["head"], "args": {"dabList": DABS}}, SAM)
    clay = d.item("head")
    assert [s["key"] for s in made(d)] == [s["key"] for s in chain(clay["steps"], d.data)]


def test_layer_after_the_base_at_its_amount_and_zero_is_gone():
    d = Document.new(KIND)
    d.run_script("head.py", run_source(SRC, "head.py"))
    shown = made(d)
    assert [s["op"] for s in shown] == ["add", "carve", "add"]          # the Base's two, then the smile
    assert abs(shown[-1]["strength"] - 0.4) < 1e-9                      # 0.8 x Amount 0.5
    d.apply({"op": "claylayer.set", "target": ["head.smile"], "args": {"amount": 0.0}}, SAM)
    assert [s["op"] for s in made(d)] == ["add", "carve"]
    base_keys = [s["key"] for s in made(d)]
    d.apply({"op": "claylayer.set", "target": ["head.smile"], "args": {"amount": 1.0}}, SAM)
    assert [s["key"] for s in made(d)][:2] == base_keys                  # the Base is never redone
    d.apply({"op": "claylayer.set", "target": ["head.smile"], "args": {"on": False}}, SAM)
    assert [s["key"] for s in made(d)] == base_keys


def test_new_strokes_go_on_the_chosen_layer_and_remove_takes_them():
    d = Document.new(KIND)
    d.apply({"op": "clay.add", "args": {"id": "head", "at": [0, 1, 0], "radius": 0.1}}, SAM)
    d.apply({"op": "claylayer.add", "target": ["head"], "args": {"name": "frown"}}, SAM)
    lay = d.item("head")["sculptLayers"][0]["id"]
    assert d.item("head")["sculptLayer"] == lay
    d.apply({"op": "clay.stroke", "target": ["head"], "args": {"dabList": DABS}}, SAM)
    assert d.item("head")["steps"][-1]["layer"] == lay
    d.apply({"op": "claylayer.remove", "target": [lay]}, SAM)
    clay = d.item("head")
    assert not clay.get("sculptLayers") and clay["sculptLayer"] == "" and len(clay["steps"]) == 1
    d.undo(SAM)                                                            # one undo step brings both back
    assert len(d.item("head")["steps"]) == 2 and d.item("head")["sculptLayers"]


def test_bake_keeps_the_shape():
    d = Document.new(KIND)
    d.run_script("head.py", run_source(SRC, "head.py"))
    before = [s["key"] for s in made(d)]
    d.apply({"op": "claylayer.bake", "target": ["head.smile"]}, SAM)
    assert not d.item("head").get("sculptLayers")
    assert [s["key"] for s in made(d)] == before


FACE = SRC.replace('head.layer("smile", amount=0.5)', 'head.layer("smile", keys={0: 0.0, 1: 1.0})')


def test_a_keyed_amount_sends_each_frame_its_own_shape():
    from rostrum3d import clay_faces
    from rostrum3d.compile import describe
    d = Document.new(KIND)
    d.run_script("head.py", run_source(FACE + 'cam = camera("cam", z=2)\nshot("s", camera=cam, fps=4, start=0, end=1)\n',
                                       "head.py"))
    scene = describe(d.data, "s")
    assert clay_faces.KEY in scene

    def ops(sc):
        return [s["op"] for s in next(n for n in sc["items"] if n["id"] == "head")["steps"]]
    first, last = clay_faces.at(scene, 0), clay_faces.at(scene, 3)
    assert clay_faces.KEY not in first and ops(first) == ["add", "carve"]       # Amount 0: the Base alone
    assert ops(last) == ["add", "carve", "add"]                                  # the smile on
    assert clay_faces.at(scene, 3) is last                                       # the same dict: "already sent" holds
    assert [r[0] for r in clay_faces.runs(scene, 0, 3)] == [0, 1, 2, 3]          # each frame a shape of its own
