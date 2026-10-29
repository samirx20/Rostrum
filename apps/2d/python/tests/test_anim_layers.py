"""Animation layers in 2D (rostrum_core.keys.layers, laid in by layerbake.py): an Add layer offsets what the engine
draws, a file without layers is described exactly as before, and a layer's keys survive save and open."""
from rostrum_core import Document, Who, storage

from rostrum2d import KIND, run_source
from rostrum2d.scene import describe

SRC = '''
comp("main", duration=2)
b = shape("box", w=100, h=100, x=400)
b.key("x", {0: 400, 2: 800}, ease="linear")
'''
SAM = Who.person("sam")


def _doc(folder=None):
    d = Document.new(KIND, folder=folder, item="main") if folder else Document.new(KIND)
    d.run_script("a.py", run_source(SRC, "a.py"))
    return d


def _box(scene):
    return next(n for n in scene["comp"]["layers"] if n["id"] == "box")


def _x_at(scene, t):
    return next(k["v"] for k in _box(scene)["anim"]["x"] if abs(k["t"] - t) < 1e-6)


def _layered(d, weight=1.0):
    d.apply({"op": "animlayer.add", "target": [], "args": {"id": "breath", "weight": weight}}, SAM)
    d.apply({"op": "key.add", "target": ["box"], "args": {"prop": "x", "t": 1.0, "v": 50, "layer": "breath"}}, SAM)
    return d


def test_an_add_layer_offsets_the_value_by_its_weight():
    d = _layered(_doc(), weight=0.5)
    assert _x_at(describe(d.data, None, None, None, None, []), 1.0) == 600 + 0.5 * 50
    d.apply({"op": "animlayer.set", "target": ["breath"], "args": {"on": False}}, SAM)
    assert [k["v"] for k in _box(describe(d.data, None, None, None, None, []))["anim"]["x"]] == [400, 800]   # off: the Base


def test_a_file_without_layers_is_described_as_before():
    d = _doc()
    before = describe(d.data, None, None, None, None, [])
    d.apply({"op": "animlayer.add", "target": [], "args": {"id": "empty"}}, SAM)          # a layer with no keys: nothing moves
    assert describe(d.data, None, None, None, None, []) == before
    assert [k["v"] for k in _box(before)["anim"]["x"]] == [400, 800]


def test_layer_keys_survive_save_and_open(tmp_path):
    (tmp_path / "docs").mkdir()
    d = _layered(_doc(tmp_path))
    d.save()
    storage.save(d, document=False)
    again = Document.open(tmp_path, "main", KIND)
    assert [x["id"] for x in again.data["animLayers"]] == ["breath"]
    assert sorted(k.get("layer") or "" for k in again.item("box")["keys"]) == ["", "", "breath"]
    assert _x_at(describe(again.data, None, None, None, None, []), 1.0) == 650
