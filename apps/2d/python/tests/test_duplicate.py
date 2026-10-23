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
    assert [c["id"] for c in layers] == ["shape_1", "shape_3", "shape_2", "group_1", "group_2"]
    assert layers[1]["name"] == "Rectangle copy" and layers[1]["effects"][0]["id"] != "blur_1"
    assert d.item("group_2")["layers"][0]["id"] == "text_2"
    d.undo(SAM)
    assert [c["id"] for c in d.item("film")["layers"]] == before
