"""A file holding parts from a plugin this Rostrum doesn't have opens (never "damaged"): the parts are kept byte for
byte on save, the header's `uses` is saved back as read, the missing plugin is named, and undo stays exact."""
import json

from rostrum_core import Document, Who, plugin_parts, toy
from rostrum_core.storage import canonical, paths

PART = {"id": "wig1", "type": "wiggle:generator", "wiggle:amount": 3, "out": [{"id": "x", "type": "rect"}], "z": {"b": 1, "a": [1.5, "é"]}}
USES = {"hiremylens.wiggle-tools": {"version": "1.2.0", "api": 1}}


def _file_with_plugin_parts(tmp_path):
    d = toy.sample(tmp_path, "main")
    d.save()
    p = paths(tmp_path, "main", toy.KIND.ext)
    f = json.loads(p["doc"].read_text(encoding="utf-8"))
    f["doc"]["layers"].append(PART)
    f["doc"]["layers"][2]["wiggle:amount"] = 5        # a plugin's setting on our own item
    f["uses"] = USES
    p["doc"].write_text(json.dumps(f), encoding="utf-8")
    return p


def test_opens_keeps_the_parts_and_names_the_plugin(tmp_path):
    p = _file_with_plugin_parts(tmp_path)
    d = Document.open(tmp_path, "main", toy.KIND)
    said = " ".join(plugin_parts.missing_of(d))
    assert "hiremylens.wiggle-tools" in said and "wig1" in said and "card.wiggle:amount" in said
    d.apply([{"op": "layer.move", "target": "card", "args": {"x": 12}}], Who.person("sam"))
    d.undo(Who.person("sam"))
    assert d.item("card")["x"] != 12
    d.apply([{"op": "layer.move", "target": "card", "args": {"x": 40}}], Who.person("sam"))
    d.save()
    f = json.loads(p["doc"].read_text(encoding="utf-8"))
    assert canonical(f["doc"]["layers"][-1]) == canonical(PART)
    assert f["doc"]["layers"][2]["wiggle:amount"] == 5 and f["uses"] == USES
    assert Document.open(tmp_path, "main", toy.KIND).item("card")["x"] == 40


def test_engines_never_see_plugin_items():
    data = {"id": "root", "type": "doc", "layers": [{"id": "a", "type": "rect"}, PART]}
    sent = plugin_parts.engine_tree(data, toy.KIND.lists)
    assert [i["id"] for i in sent["layers"]] == ["a"] and len(data["layers"]) == 2
    plain = {"id": "root", "type": "doc", "layers": [{"id": "a", "type": "rect"}]}
    assert plugin_parts.engine_tree(plain, toy.KIND.lists) is plain


def test_a_file_without_plugins_saves_no_uses(tmp_path):
    d = toy.sample(tmp_path, "main")
    d.save()
    assert "uses" not in json.loads(paths(tmp_path, "main", toy.KIND.ext)["doc"].read_text(encoding="utf-8"))
