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


def test_times_with_a_step_makes_a_row_in_one_undo_step():
    """layer.duplicate {by_x, times}: copies at +100, +200, +300 from the original, each above the one before, one undo."""
    d = _doc()
    d.apply({"op": "layer.duplicate", "target": ["shape_1"], "args": {"by_x": 100, "times": 3}}, SAM)
    ids = [c["id"] for c in d.item("film")["layers"]]
    assert ids[1:5] == ["shape_1", "shape_3", "shape_4", "shape_5"]
    assert [d.item(i)["x"] for i in ids[1:5]] == [960, 1060, 1160, 1260]
    d.undo(SAM)
    assert len(d.item("film")["layers"]) == 4


def test_many_copies_in_one_call_keep_ids_names_and_places_apart():
    """One call copying many layers (Alt+drag of all, Ctrl+D of all) works out ids, names and taken places once and
    keeps them up to date: no copy takes another's id or name, and each still steps off the copies made before it."""
    d = _doc()
    d.apply({"op": "layer.duplicate", "target": ["shape_1", "shape_2"]}, SAM)       # both at 960, 540
    layers = d.item("film")["layers"]
    assert [c["id"] for c in layers][:5] == ["frame", "shape_1", "shape_3", "shape_2", "shape_4"]
    assert [(d.item(i)["x"], d.item(i)["y"]) for i in ("shape_3", "shape_4")] == [(984, 564), (1008, 588)]
    d.apply({"op": "layer.duplicate", "target": ["shape_1", "shape_3", "shape_2"], "args": {"by_x": 0}}, SAM)
    ids = [c["id"] for c in d.item("film")["layers"]]
    names = [c["name"] for c in d.item("film")["layers"] if c["name"].endswith(("copy", "copy 2", "copy 3", "copy 4"))]
    assert len(ids) == len(set(ids)) == 9 and len(names) == len(set(names)) == 5
    assert ids.index("shape_5") == ids.index("shape_1") + 1 and ids.index("shape_7") == ids.index("shape_2") + 1
