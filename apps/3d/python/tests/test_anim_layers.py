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


def test_k_on_an_add_layer_keys_offsets_and_changes_nothing_seen():
    """key.add `fields` (K) with a layer keys each field's own curve now (add: 0 where it has none), never the whole
    value (which on an add layer would double it); the shared rule the window's route uses too (layers.key_for)."""
    from rostrum_core import Param, Registry
    from rostrum_core.keys import layers, register_key_ops, register_layer_ops
    from rostrum_core.kind import DocKind
    r = Registry()

    @r.operation("object.add", "Add", target="doc", params=[Param.text("id", label="Id", required=True)])
    def object_add(ctx, targets, args):
        ctx.insert("root", "objects", {"id": args["id"], "type": "object", "x": 2.0, "y": 1.0, "keys": []}, None)
    register_key_ops(r, owners=["object"], check_key=lambda ctx, o, p, a: ("v", float(a["v"])),
                     check_still=lambda ctx, o, p, a: float(a["v"]), field_sets={"pose": ["x", "y"]},
                     value_now=lambda ctx, o, p, t: {"v": layers.base_at(o, p, t)}, layers=True)
    register_layer_ops(r)
    kind = DocKind("k", ".k", r, lists=layers.with_lists({"doc": ["objects"], "object": ["keys"]}),
                   new=lambda: {"id": "root", "type": "doc", "objects": []})
    d = Document.new(kind)
    _do(d, "object.add", ["root"], id="o")
    _do(d, "animlayer.add", id="bob", weight=0.5)
    _do(d, "key.add", ["o"], prop="x", t=1, v=0.4, layer="bob")
    shown = lambda p, t: layers.shown_at(d.item("o"), p, t, layers.stack_of(d.data))    # noqa: E731
    before = (shown("x", 0), shown("y", 0))
    _do(d, "key.add", ["o"], fields="pose", t=0, layer="bob")
    assert (shown("x", 0), shown("y", 0)) == before == (2.2, 1.0)
    assert d.item("o.y.bob.k0")["v"] == 0 and d.item("o.x.bob.k0")["v"] == 0.4      # offsets, not 1.0 / 2.2
    # the window's rule: the key that shows 3.0 at 0.5 weight is the curve now + what is missing over the weight
    assert layers.key_for(d.item("o"), "x", 0, layers.stack_of(d.data), "bob", 3.0) == 2.0


def test_stagger_moves_layer_keys_and_ignores_the_base_at_that_time():
    d = _doc()
    _do(d, "animlayer.add", id="breath")
    _do(d, "key.add", ["ball"], prop="y", t=0, v=0.1, layer="breath")
    _do(d, "key.add", ["lamp"], prop="intensity", t=0, v=1, layer="breath")
    _do(d, "key.add", ["lamp"], prop="intensity", t=0.5, v=3)                          # a Base key where it lands
    _do(d, "key.stagger", ["ball.y.breath.k0", "lamp.intensity.breath.k0"], by=0.5, order="picked")
    assert d.item("lamp.intensity.breath.k0")["t"] == 0.5 and d.item("ball.y.breath.k0")["t"] == 0
    assert d.item("lamp.intensity.k500")["t"] == 0.5 and [k["t"] for k in d.item("ball")["keys"] if not k.get("layer")] == [0, 1]


def test_pose_drag_on_a_layer_leaves_the_base_and_shows_the_pose(tmp_path):
    """The same two drags, the second on a half-weight add layer: the Base keeps the first, and what shows is the
    same pose as dragging twice on the Base (the drag started from the pose shown and keyed offsets)."""
    from rostrum3d import ops_pose, pose_ik
    from rostrum_core.keys import layers
    from test_pose import _doc as clay_doc
    drag = {"part": "forearm.L", "holds": ["foot.L", "foot.R"], "at": 0.5}
    shown = []
    for n, layer in enumerate(({}, {"layer": "lift"})):
        d = clay_doc(tmp_path / str(n))
        d.apply({"op": "pose.drag", "target": ["c"], "args": {**drag, "to": [0.4, 0.8, 0.1]}}, SAM)
        base = {k["id"]: k["v"] for b in ops_pose._all_bones(d.item("c")) for k in b.get("keys", [])}
        _do(d, "animlayer.add", id="lift", weight=0.5)
        d.apply({"op": "pose.drag", "target": ["c"], "args": {**drag, "to": [0.5, 0.9, 0.1], **layer}}, SAM)
        shown.append(pose_ik.Rig(d.item("c"), 0.5, layers.stack_of(d.data)).turn)
    keys = [k for b in ops_pose._all_bones(d.item("c")) for k in b.get("keys", [])]
    assert {k["id"]: k["v"] for k in keys if not k.get("layer")} == base                # the Base untouched
    assert any(k.get("layer") == "lift" for k in keys)
    assert all(abs(a - b) < 1e-4 for x, y in zip(*shown) for a, b in zip(x, y))
    ops_pose.use_grid(None)


def test_base_under_layers_shows_what_was_set():
    """Editing the Base while an Add layer moves the field: the Base gets the value that shows what was set."""
    from rostrum_core.keys import layers as L
    owner = {"id": "ball", "z": 0.0, "keys": [{"id": "k1", "type": "key", "prop": "z", "t": 0.0, "v": 0.3, "layer": "br"}]}
    stack = [{"id": "br", "type": "animLayer", "weight": 0.5, "mode": "add", "on": True}]
    base = L.base_for(owner, "z", 0.0, stack, 1.0)
    assert abs(L.value(owner, "z", 0.0, stack, base) - 1.0) < 1e-9
    stack[0]["mode"] = "replace"
    base = L.base_for(owner, "z", 0.0, stack, 1.0)
    assert abs(L.value(owner, "z", 0.0, stack, base) - 1.0) < 1e-9
