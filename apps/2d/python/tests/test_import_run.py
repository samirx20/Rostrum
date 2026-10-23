"""run_import (the Import panel's and the MCP tool's one door): an SVG goes in as ONE undo step and the report comes back."""
import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, settings
from rostrum2d.engine import EngineError, find_exe
from rostrum2d.io import importing

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
  <defs><clipPath id="c"><circle cx="100" cy="100" r="50"/></clipPath></defs>
  <rect id="bg" width="400" height="300" fill="#102030"/>
  <g clip-path="url(#c)"><rect id="dot" x="60" y="60" width="80" height="80" fill="#ff0000"/></g>
</svg>"""


def test_run_import_is_one_undo_step_with_report(tmp_path):
    try:
        find_exe()
    except EngineError:
        pytest.skip(settings.engine_missing_reason())
    (tmp_path / "t.svg").write_text(SVG, encoding="utf-8")
    doc, me = Document.new(KIND, folder=str(tmp_path / "doc"), item="t"), Who.agent("test")
    doc.apply([{"op": "comp.add", "args": {"id": "c", "width": 400, "height": 300}}], me)
    r = importing.run(doc, me, "c", tmp_path / "t.svg")
    assert r["layers"] == ["bg", "dot"] and r["calls"] == 4 and any("clip" in line for line in r["report"])
    doc.undo(me)
    assert doc.item("c")["layers"] == []
    with pytest.raises(ValueError, match="no file"):
        importing.run(doc, me, "c", tmp_path / "missing.svg")
    assert doc.item("c")["layers"] == []
