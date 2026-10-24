"""SVG import keeps the source's layers: names, order, the group, path geometry in place (engine's svg-tree)."""
import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, settings
from rostrum2d.engine import EngineError, find_exe
from rostrum2d.io import import_into, svg_tree

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
  <rect id="bg" width="400" height="300" fill="#102030"/>
  <g id="pair" opacity="0.5"><circle id="dot" cx="100" cy="100" r="20" fill="#ff0000"/>
    <rect id="bar" x="200" y="150" width="50" height="10" fill="#00ff00" fill-opacity="0.5"/></g>
</svg>"""


def test_svg_round_trip(tmp_path):
    try:
        find_exe()
    except EngineError:
        pytest.skip(settings.engine_missing_reason())
    (tmp_path / "t.svg").write_text(SVG, encoding="utf-8")
    doc = Document.new(KIND, folder=str(tmp_path / "doc"), item="t")
    me = Who.agent("test")
    doc.apply([{"op": "comp.add", "args": {"id": "c", "width": 400, "height": 300}}], me)
    import_into(doc, svg_tree(tmp_path / "t.svg"), "c", me)
    _frame, bg, pair = doc.data["comps"][0]["layers"]
    assert (bg["id"], pair["id"], pair["opacity"]) == ("bg", "pair", 0.5)
    dot, bar = pair["layers"]
    assert (dot["id"], dot["type"], bar["opacity"]) == ("dot", "path", pytest.approx(0.5, abs=0.01))
    assert (pair["x"] + dot["x"], pair["y"] + dot["y"]) == pytest.approx((80, 80), abs=0.01)   # the circle's box, in place
