"""A new shape is named for its kind and numbered per kind from 1 ("Rectangle", "Ellipse", "Ellipse 2"), never by how many
layers there already are; a name a person typed stays."""
from rostrum_core import Document, Who

from rostrum2d import KIND
from rostrum2d.names import display_name

SAM = Who.person("sam")


def test_shape_names_count_per_kind():
    d = Document.new(KIND)
    calls = [{"op": "comp.add", "args": {"id": "film"}}]
    for id_, kind in (("a", "rect"), ("b", "ellipse"), ("c", "ellipse")):
        calls += [{"op": "layer.add", "target": "film", "args": {"type": "shape", "id": id_}},
                  {"op": "shape.set", "target": id_, "args": {"shape": kind}}]
    d.apply(calls, SAM)
    assert [display_name(d.item(i)) for i in "abc"] == ["Rectangle", "Ellipse", "Ellipse 2"]
    d.apply([{"op": "item.rename", "target": "a", "args": {"name": "Logo"}},
             {"op": "shape.set", "target": "a", "args": {"shape": "star"}}], SAM)
    assert display_name(d.item("a")) == "Logo"
