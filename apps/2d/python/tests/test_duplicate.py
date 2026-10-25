"""layer.duplicate: the copy sits just above, with new ids all the way down, and one undo takes it away. New layers get names in words."""
from rostrum_core import Document, Who

from rostrum2d import KIND

SAM = Who.person("sam")


def _doc():
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape"}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape"}},
             {"op": "layer.add", "target": "film", "args": {"type": "group"}},
             {"op": "layer.add", "target": "group_1", "args": {"type": "text"}}], SAM)
    d.apply([{"op": "effect.add", "target": "shape_1", "args": {"type": "blur"}}], SAM)
    return d


def test_names_in_words():
    d = _doc()
    assert [d.item(i)["name"] for i in ("shape_1", "shape_2", "group_1", "text_1")] == ["Shape", "Shape 2", "Group", "Text"]


def test_duplicate_is_one_undo_step_with_new_ids():
    d = _doc()
    before = [c["id"] for c in d.item("film")["layers"]]
    d.apply({"op": "layer.duplicate", "target": ["shape_1", "group_1"]}, SAM)
    layers = d.item("film")["layers"]
    assert [c["id"] for c in layers] == ["frame", "shape_1", "shape_3", "shape_2", "group_1", "group_2"]
    assert layers[2]["name"] == "Rectangle copy" and layers[2]["effects"][0]["id"] != "blur_1"
    assert d.item("group_2")["layers"][0]["id"] == "text_2"
    d.undo(SAM)
    assert [c["id"] for c in d.item("film")["layers"]] == before


def test_copies_never_sit_exactly_on_another_and_paste_across_scenes_is_one_undo():
    """One rule for Duplicate and Paste (ops_nudge.py): a taken place steps 24 px right and down; another scene keeps it."""
    import json
    d = _doc()
    d.apply({"op": "layer.duplicate", "target": ["shape_1"]}, SAM)
    d.apply({"op": "layer.duplicate", "target": ["shape_1"]}, SAM)
    spots = [(d.item(i)["x"], d.item(i)["y"]) for i in ("shape_1", "shape_3", "shape_4")]
    assert spots == [(960, 540), (984, 564), (1008, 588)]
    copied = json.dumps([d.item("shape_1")])
    d.apply({"op": "layer.paste", "args": {"layers": copied, "into": "film"}}, SAM)
    assert (d.item("shape_5")["x"], d.item("shape_5")["y"]) == (1032, 612)
    d.apply({"op": "comp.add", "args": {"id": "two"}}, SAM)
    n = len(d.item("two")["layers"])
    d.apply({"op": "layer.paste", "args": {"layers": copied, "into": "two"}}, SAM)
    assert d.item("two")["layers"][-1]["x"] == 960 and len(d.item("two")["layers"]) == n + 1
    d.undo(SAM)
    assert len(d.item("two")["layers"]) == n
