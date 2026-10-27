"""Varied copies: layer.duplicate with vary_* ranges. The same seed gives the same copies, another seed others, and every
copy is an ordinary layer (plain values and keys; undo takes the whole call back in one step)."""
import copy

from rostrum_core import Document, Who

from rostrum2d import KIND, run_source

SRC = '''
comp("c", width=640, height=360, duration=4)
s = shape("box", w=80, h=40, x=100, y=100, fill="#c04030")
s.key("x", {1.0: 100, 2.0: 200})
'''
AGENT = Who.agent("tester")
ARGS = {"times": 3, "by_x": 120, "seed": 7, "vary_scale": 0.3, "vary_turn": 15, "vary_hue": 40, "vary_light": 0.1, "vary_opacity": 0.2, "vary_time": 0.5}


def _copies(seed):
    d = Document.new(KIND)
    d.run_script("t.py", run_source(SRC, "t.py"))
    before = copy.deepcopy(d.data)
    d.apply({"op": "layer.duplicate", "target": ["box"], "args": {**ARGS, "seed": seed}}, AGENT)
    out = [{k: v for k, v in l.items() if k not in ("id", "name", "layers", "keys")} | {"t": [k["t"] for k in l.get("keys", [])]}
           for l in d.item("c")["layers"] if l["id"] != "box" and l["type"] == "shape"]
    return d, before, out


def test_same_seed_same_copies_each_an_ordinary_layer_and_undo_restores():
    d, before, a = _copies(7)
    _, _, b = _copies(7)
    _, _, c = _copies(8)
    assert a == b and a != c and len(a) == 3
    assert len({x["scale"] for x in a}) == 3 and len({x["fill"] for x in a}) == 3          # each copy its own
    assert all(0 <= x["opacity"] <= 1 and 0.5 <= x["t"][0] <= 1.5 for x in a)               # inside the ranges; keys shifted with the copy
    d.apply({"op": "shape.set", "target": ["shape_2"], "args": {"scale": 2}}, AGENT)        # an ordinary layer: editable
    d.undo(AGENT)
    d.undo(AGENT)
    assert d.data == before
