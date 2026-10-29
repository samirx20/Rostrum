"""Animation layers (rostrum_core.keys.layers): what would break silently is a layer that changes the picture wrongly
(add / replace / weight / off), an old file that reads differently, a removed layer leaving its keys behind, an undo
that leaves half a layer, or an agent's re-run wiping a person's layer."""
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe

SAM = Who.person()
SRC = '''
ball = mesh("ball", shape="sphere", radius=0.2)
ball.key("y", {0: 0, 1: 2})
lamp = light("lamp", kind="rect", intensity=2, y=2, color="#ffffff")
cam = camera("cam", z=4).aim(ball)
shot("one", camera=cam, end=1)
'''


def _doc():
    d = Document.new(KIND, None, None)
    d.run_script("scene.py", run_source(SRC, "scene.py", d))
    return d


def _do(d, op, target=(), **args):
    d.apply({"op": op, "target": list(target), "args": args}, SAM)


def _anim(d, id_, prop):
    stack = list(describe(d.data, "one")["items"])
    while stack:
        n = stack.pop()
        if n["id"] == id_:
            return n.get("anim", {}).get(prop) or [n["props"][prop]] * 25
        stack += n.get("children", [])


def test_add_replace_weight_and_off():
    d = _doc()
    base = _anim(d, "ball", "y")
    _do(d, "animlayer.add", id="breath", name="Breath")
    _do(d, "key.add", ["ball"], prop="y", t=0, v=0.5, layer="breath")
    assert all(abs(a - (b + 0.5)) < 1e-6 for a, b in zip(_anim(d, "ball", "y"), base))     # add: an offset on top
    _do(d, "animlayer.set", ["breath"], weight=0.5)
    assert all(abs(a - (b + 0.25)) < 1e-6 for a, b in zip(_anim(d, "ball", "y"), base))
    _do(d, "animlayer.set", ["breath"], mode="replace", weight=1.0)
    assert all(abs(a - 0.5) < 1e-6 for a in _anim(d, "ball", "y"))                         # replace: the layer's value
    _do(d, "animlayer.set", ["breath"], on=False)
    assert _anim(d, "ball", "y") == base
    # a still field gets a layer too; a colour under replace mixes, under add stays the Base
    _do(d, "animlayer.set", ["breath"], on=True, weight=0.5)
    _do(d, "key.add", ["lamp"], prop="intensity", t=0, v=4, layer="breath")
    assert abs(_anim(d, "lamp", "intensity")[0] - 3) < 1e-6 and d.item("lamp")["intensity"] == 2


def test_weight_keys_fade_a_layer_in():
    d = _doc()
    _do(d, "animlayer.add", id="breath")
    _do(d, "key.add", ["lamp"], prop="intensity", t=0, v=1, layer="breath")
    _do(d, "animlayer.set", ["breath"], weight=0, at=0)
    _do(d, "animlayer.set", ["breath"], weight=1, at=1)
    seen = _anim(d, "lamp", "intensity")
    assert abs(seen[0] - 2) < 1e-6 and seen[-1] > 2.99 and 2 < seen[len(seen) // 2] < 3


def test_old_file_unchanged_and_base_keys_untouched():
    d = _doc()
    before, base = describe(d.data, "one"), [k["v"] for k in d.item("ball")["keys"]]
    _do(d, "animlayer.add", id="breath")
    _do(d, "key.add", ["ball"], prop="y", t=1, v=9, layer="breath")
    _do(d, "animlayer.set", ["breath"], weight=0)
    assert describe(d.data, "one") == before                            # weight 0 = the file without the layer
    assert [k["v"] for k in d.item("ball")["keys"] if not k.get("layer")] == base   # same time, own key: Base kept


def test_remove_takes_its_keys_and_undo_is_one_step():
    d = _doc()
    _do(d, "animlayer.add", id="breath")
    _do(d, "key.add", ["ball"], prop="y", t=0.5, v=1, layer="breath")
    _do(d, "animlayer.remove", ["breath"])
    assert "breath" not in str(d.data)
    d.undo(SAM)
    assert d.item("ball.y.breath.k500")["layer"] == "breath" and d.data["animLayers"][0]["id"] == "breath"
    d.undo(SAM)
    assert not any(k.get("layer") for k in d.item("ball")["keys"])


def test_move_and_unknown_layer_is_refused():
    d = _doc()
    _do(d, "animlayer.add", id="a")
    _do(d, "animlayer.add", id="b")
    _do(d, "animlayer.move", ["b"], to=0)
    assert [x["id"] for x in d.data["animLayers"]] == ["b", "a"]
    try:
        _do(d, "key.add", ["ball"], prop="y", t=0, v=1, layer="nope")
        raise AssertionError("refused")
    except Exception as e:                                    # noqa: BLE001
        assert "nope" in str(e)


def test_a_rerun_keeps_a_persons_layer():
    d = _doc()
    _do(d, "animlayer.add", id="breath")
    _do(d, "key.add", ["ball"], prop="y", t=0, v=0.3, layer="breath")
    d.run_script("scene.py", run_source(SRC.replace("{0: 0, 1: 2}", "{0: 0, 1: 3}"), "scene.py", d))
    assert d.item("ball.y.breath.k0")["v"] == 0.3 and d.data["animLayers"][0]["id"] == "breath"
    assert _anim(d, "ball", "y")[-1] > 3.2
