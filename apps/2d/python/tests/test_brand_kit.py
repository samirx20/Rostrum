"""The project's brand kit (brand_kit.py): what is added is read back by every document of the project, and a kit text
style used twice refreshes the document's one style of that name (never a second copy), so a brand change reaches
every text that follows it. Silent breakage: a kit that forgets entries, or texts left on an old brand look."""
from rostrum_core import Document, Who

from rostrum2d import KIND, brand_kit

SAM = Who.person("sam")


def test_kit_style_used_twice_refreshes_one_document_style(tmp_path):
    brand_kit.add(tmp_path, "textStyles", {"name": "Heading", "size": 80, "color": "#112233"})
    brand_kit.add(tmp_path, "colors", {"name": "Brand blue", "value": "#1d4ed8"})
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "s"}},
             {"op": "layer.add", "target": "s", "args": {"type": "text", "id": "a"}},
             {"op": "layer.add", "target": "s", "args": {"type": "shape", "id": "box"}}], SAM)
    d.apply(brand_kit.use_calls(d, "textStyles", brand_kit.entry(tmp_path, "textStyles", "Heading"), ["a"]), SAM)
    assert d.item("a")["size"] == 80 and d.item("a")["textStyle"]
    brand_kit.add(tmp_path, "textStyles", {"name": "Heading", "size": 64})               # the brand changes
    d.apply(brand_kit.use_calls(d, "textStyles", brand_kit.entry(tmp_path, "textStyles", "Heading"), ["a"]), SAM)
    assert [s["name"] for s in d.data["textStyles"]] == ["Heading"] and d.item("a")["size"] == 64
    d.apply(brand_kit.use_calls(d, "colors", brand_kit.entry(tmp_path, "colors", "Brand blue"), ["box"]), SAM)
    assert d.item("box")["fill"] == "#1d4ed8"
    assert [c["name"] for c in brand_kit.read(tmp_path)["colors"]] == ["Brand blue"]
