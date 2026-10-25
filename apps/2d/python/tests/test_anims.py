"""anim.list's lines (anims.py, what the timeline draws too): overlapping animations of one layer go on separate lines,
non-overlapping ones share line 0, X and Y are one animation; anim.ease eases whole stretches in one undo step."""
from rostrum_core import Document, Who
from rostrum_core.keys.easing import EASE_LIST

from rostrum2d import KIND
from rostrum2d.anims import animations

SAM = Who.person("sam")


def _key(owner, prop, t, v, ease="smooth"):
    return {"op": "key.add", "target": owner, "args": {"prop": prop, "t": t, "v": v, "ease": ease}}


def _doc():
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "fps": 30, "duration": 10}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "title"}},
             _key("title", "x", 1.0, 760), _key("title", "x", 2.0, 960), _key("title", "y", 1.0, 542), _key("title", "y", 2.0, 482),
             _key("title", "opacity", 1.5, 0), _key("title", "opacity", 2.5, 1),      # overlaps Position: line 1
             _key("title", "scale", 3.2, 1), _key("title", "scale", 3.8, 1.2)], SAM)   # after both: line 0
    return d


def test_lines_pack_overlap_apart_and_the_rest_together():
    lines = {a["setting"]: a["line"] for a in animations(_doc().item("title"))}
    assert lines == {"position": 0, "opacity": 1, "scale": 0}
    pos = next(a for a in animations(_doc().item("title")) if a["setting"] == "position")
    assert pos["props"] == ["x", "y"] and pos["stretches"][0]["from"] == {"x": 760, "y": 542}
    assert sorted(pos["stretches"][0]["ids"]) == ["title.x.k1000", "title.y.k1000"]


def test_ease_is_one_undoable_change():
    d = _doc()
    ids = ["title.x.k1000", "title.y.k1000"]
    d.apply({"op": "anim.ease", "target": ids, "args": {"preset": "out"}}, SAM)
    assert {d.item(i)["ease"] for i in ids} == {"easeOut"}
    d.undo(SAM)
    assert {d.item(i)["ease"] for i in ids} == {"smooth"}


def test_every_ease_in_the_one_list_round_trips():
    """EASE_LIST (base E): each id goes in through key.set {ease} and anim.ease {preset} and comes back the same, with
    its label, from the animation reading (anim.list / inspect); the first words "in" and "out" still work."""
    d = _doc()
    ids = ["title.x.k1000", "title.y.k1000"]
    for e in EASE_LIST:
        for call in ({"op": "key.set", "target": ids, "args": {"ease": e["id"]}},
                     {"op": "anim.ease", "target": ids, "args": {"preset": e["id"]}}):
            d.apply(call, SAM)
            s = next(a for a in animations(d.item("title")) if a["setting"] == "position")["stretches"][0]
            assert (s["ease"], s["easeLabel"]) == (e["id"], e["label"])
    for old, ease in (("in", "easeIn"), ("out", "easeOut")):
        d.apply({"op": "anim.ease", "target": ids, "args": {"preset": old}}, SAM)
        assert {d.item(i)["ease"] for i in ids} == {ease}
