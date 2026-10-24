"""Imports: what must hold round trip (layer count, names, order, a group, one PSD pixel, one place) and what an
import must say rather than drop. Seconds to run."""
import json
from pathlib import Path

import pytest
from PIL import Image
from rostrum_core import Document
from rostrum_core.who import Who

from rostrum2d.io import tree as T
from rostrum2d.io.figma import frame_tree
from rostrum2d.io.pdf import pdf_tree
from rostrum2d.io.psd import psd_tree
from rostrum2d.kind import KIND

ME = Who.agent("test")
HERE = Path(__file__).parent


def _doc(tmp_path):
    doc = Document.new(KIND, folder=tmp_path)
    doc.apply([{"op": "comp.add", "args": {"id": "c", "width": 800, "height": 600}}], ME)
    return doc


def _top(doc):
    return [l for l in doc.data["comps"][0]["layers"] if l["type"] != "camera"]     # the layers, not the scene's frame


def _psd(tmp_path):
    from psd_tools import PSDImage
    from psd_tools.api.layers import Group, PixelLayer
    from psd_tools.constants import BlendMode
    psd = PSDImage.new("RGBA", (200, 100), color=(0, 0, 0, 255))
    PixelLayer.frompil(Image.new("RGBA", (50, 40), (255, 0, 0, 255)), psd, name="Red", top=10, left=20).opacity = 128
    PixelLayer.frompil(Image.new("RGBA", (30, 30), (0, 0, 255, 255)), psd, name="Blue", top=50, left=100).blend_mode = BlendMode.MULTIPLY
    g = Group.new(psd, name="Box")
    PixelLayer.frompil(Image.new("RGBA", (10, 10), (0, 255, 0, 255)), g, name="Green", top=5, left=150)
    psd.save(tmp_path / "t.psd")
    return tmp_path / "t.psd"


def test_psd_layers_come_in_with_names_order_group_and_pixels(tmp_path):
    doc = _doc(tmp_path)
    report = T.import_into(doc, psd_tree(_psd(tmp_path)), "c", ME)
    top = _top(doc)
    assert [(l["name"], l["type"]) for l in top] == [("Red", "image"), ("Blue", "image"), ("Box", "group")]
    assert (top[0]["opacity"], top[1]["blend"]) == (pytest.approx(0.5, abs=0.01), "multiply")
    assert [l["name"] for l in top[2]["layers"]] == ["Green"]
    assert (top[0]["x"], top[0]["y"], top[2]["layers"][0]["x"]) == (20, 10, 0)
    assert Image.open(top[1]["src"]).convert("RGBA").getpixel((5, 5)) == (0, 0, 255, 255)
    assert report == []
    doc.undo(ME)
    assert _top(doc) == []                                 # one undo step takes the whole import out


def test_figma_sample_maps_and_reports_what_it_leaves(tmp_path):
    sample = json.loads((HERE / "data" / "figma_sample.json").read_text(encoding="utf-8"))
    tr = frame_tree(sample, "Poster", render=lambda node: Image.new("RGBA", (100, 60), (9, 9, 9, 255)))
    doc = _doc(tmp_path)
    report = T.import_into(doc, tr, "c", ME, fonts={"Roboto Flex"})
    top = _top(doc)
    assert [l["name"] for l in top] == ["Poster background", "Card", "Sun", "Title", "Wave", "Badge", "Hidden"]
    assert top[0]["type"] == "shape" and top[4]["type"] == "path" and top[5]["type"] == "group"
    assert [l["name"] for l in top[5]["layers"]] == ["Badge ring", "Photo"]
    assert (top[1]["x"], top[1]["y"]) == (80, 320) and top[1]["opacity"] == pytest.approx(0.5, abs=0.01)   # frame origin subtracted; fill alpha folded in
    assert top[3]["font"] == "Roboto Flex" and top[6]["hidden"] is True
    assert "C" in top[4]["d"] and "Q" not in top[4]["d"]
    assert any("Inter" in r for r in report) and tr["notes"] == ["Kept hidden, as in the file: Hidden"]


def test_a_field_that_is_not_in_fields_py_is_an_error():
    bad = {"name": "x", "layers": [{"type": "shape", "name": "s", "box": [0, 0, 5, 5], "props": {"glitter": 1}}]}
    with pytest.raises(ValueError, match="glitter"):
        T.apply_calls(bad, {"id": "root", "comps": []}, "c")


def test_pdf_page_becomes_path_text_and_a_group(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_sources", HERE.parents[3] / "proofs" / "2d-io" / "make_sources.py")
    ms = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ms)
    ms.make_pdf(tmp_path / "t.pdf")
    doc = _doc(tmp_path)
    T.import_into(doc, pdf_tree(tmp_path / "t.pdf"), "c", ME)
    top = _top(doc)
    assert [l["type"] for l in top] == ["path", "path", "path", "path", "group", "text"]
    assert [l["type"] for l in top[4]["layers"]] == ["path", "path"]
    assert (top[1]["x"], top[1]["y"], top[1]["fill"]) == (80, 320, "#ff6b6b")   # y flipped: PDF y 100..280 → 320..500
    assert top[5]["body"] == "Hello Rostrum" and top[5]["size"] == 64


def test_a_scene_with_no_project_folder_still_takes_a_psd_and_masks_are_not_losses(tmp_path):
    doc = Document.new(KIND)                               # not in a project yet: no folder to write the pictures into
    doc.apply([{"op": "comp.add", "args": {"id": "c", "width": 800, "height": 600}}], ME)
    tr = psd_tree(_psd(tmp_path))
    T.import_into(doc, tr, "c", ME)
    assert Image.open(_top(doc)[1]["src"]).size == (30, 30)        # the picture is on disk, named by its own path
    tr["report"].extend(["text 'a': the font 'X' is not here", "text 'b': the font 'X' is not here"])
    assert [r for r in T.collapse(tr["report"])] == ["The font 'X' is not here (2 layers: a, b)"]
