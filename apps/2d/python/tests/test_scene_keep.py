"""The screen describes a change through scene_keep.Keeper: after every kind of edit its description equals
scene.describe's (anything else draws a stale or wrong picture without a word), and an untouched layer's node is the
previous call's own object (what lets the engine be sent only the change). And the change message Engine.load sends
(scene_change.py) stands for exactly the full scene."""
from rostrum_core import Document, Who

from rostrum2d import KIND, run_source, scene_change
from rostrum2d.scene import describe
from rostrum2d.scene_keep import Keeper

SAM = Who.person("sam")
MARKS = {"drop": 0.5}
SRC = '''
comp("film", fps=10, duration=2)
a = shape("a", w=10, h=10)
a.key("x", {0: 0, 2: 100})
b = shape("b", w=10, h=10)
c = shape("c", w=10, h=10)
c.effect("shadow", dy=4)
g = group("g", background=True)
with g:
    for i in range(6):
        shape(f"k{i}", w=5, h=5, x=i * 10)
'''


def _layer(scene, id_):
    return next(n for n in scene["comp"]["layers"] if n["id"] == id_)


def _edits(d):
    """(what, do it): every kind of change the screen meets."""
    set_ = lambda t, **v: lambda: d.apply({"op": "shape.set", "target": t, "args": v}, SAM)

    def drag():
        with d.gesture("Move b", SAM) as g:
            for x in (10, 20, 30):
                g.preview({"op": "value.set", "target": "b", "args": {"prop": "x", "v": x}})
                yield
        yield
    return [("field", set_("b", w=40)), ("drag", drag),
            ("key", lambda: d.apply({"op": "key.add", "target": "c", "args": {"prop": "y", "t": 1, "v": 50}}, SAM)),
            ("child", set_("k3", h=9)),
            ("pin", lambda: d.apply({"op": "layer.pin", "target": ["b"], "args": {"on": True, "keep": "shown", "at": 1.0}}, SAM)),
            ("undo", lambda: d.undo(SAM)), ("redo", lambda: d.redo(SAM)),
            ("add", lambda: d.apply({"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "n"}}, SAM)),
            ("reorder", lambda: d.apply({"op": "layer.arrange", "target": "n", "args": {"index": 0}}, SAM)),
            ("remove", lambda: d.apply({"op": "layer.remove", "target": "n"}, SAM)),
            ("group", lambda: d.apply({"op": "group.make", "target": ["k0", "k1"], "args": {"id": "pair"}}, SAM)),
            ("expression", lambda: d.apply({"op": "expr.set", "target": "c", "args": {"prop": "x", "source": "time * 20"}}, SAM)),
            ("marker", set_("b", marker="drop")), ("marker child", set_("k4", w=7)),
            ("swap", lambda: d.apply({"op": "group.set", "target": "g", "args": {"swap": True, "show": 2}}, SAM)),
            ("stepped", set_("c", timing="2")), ("stepped comp", lambda: d.apply(
                {"op": "comp.set", "target": "film", "args": {"timing": "3"}}, SAM))]


def test_kept_description_equals_describe_after_every_edit():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    keep = Keeper()
    args = (None, MARKS, None, (0.0, 2.0))
    last = keep.describe(d.data, *args, [])
    for what, edit in _edits(d):
        steps = edit()
        for _ in (steps if hasattr(steps, "__next__") else [None]):
            got = keep.describe(d.data, *args, [])
            assert got == describe(d.data, *args, []), what
            if what != "stepped comp":                  # (that one changes how every layer is sent)
                assert _layer(got, "a") is _layer(last, "a"), what                   # untouched: the same object
            if what == "child":
                kids = {n["id"]: n for n in _layer(got, "g")["layers"]}
                assert kids["k2"] is {n["id"]: n for n in _layer(last, "g")["layers"]}["k2"]   # a sibling at depth
            last = got


def test_change_message_expands_to_the_full_scene():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    keep = Keeper()
    held = keep.describe(d.data, None, MARKS, None, (0.0, 2.0), [])
    d.apply({"op": "shape.set", "target": "k3", "args": {"h": 9}}, SAM)
    new = keep.describe(d.data, None, MARKS, None, (0.0, 2.0), [])
    req, why = scene_change.request(held, new)
    assert why is None and "change" in req
    layers = req["change"]["comp"]["layers"]
    group = next(n for n in layers if isinstance(n, dict) and n["id"] == "g")
    assert "a" in layers and "k2" in group["layers"]           # kept nodes go as their ids, at any depth
    assert scene_change.expand(req["change"], held) == new
    assert scene_change.request(held, describe(d.data, None, MARKS, None, (0.0, 2.0), []))[0].keys() == {"scene"}
