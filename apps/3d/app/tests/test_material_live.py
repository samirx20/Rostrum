"""A material's line-width drag (brief 22) would break silently: with the window's view live, each move is one light
`material` request (colours linear, as the scene sends them) and the document changes once, at the release; in the
Final look it falls back to the document preview. No viewport or engine."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.colors import linear  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402

SRC = '''
cam = camera("cam", z=3)
ink = material("ink", lines=True)
mesh("case", shape="box", material=ink)
shot("s", camera=cam, fps=10, start=0, end=2)
'''


class Link:
    item = object()

    def __init__(self):
        self.sent = []

    def post(self, req, then, scene=None):
        self.sent.append(req)
        then({"ok": True, "ms": 1.0})


@pytest.fixture
def bridge():
    QGuiApplication.instance() or QGuiApplication([])
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    b = Bridge3D(doc, viewport=None)
    yield b
    b.viewport = None
    b.close()


def test_a_width_drag_is_live_and_one_undo_step(bridge):
    bridge.select("ink")
    link = bridge.viewport = SimpleNamespace(link=Link(), look="quick")
    n = len(bridge.doc.history.changes)
    bridge.beginScrub("linesWidth")
    for v in (2.0, 3.0, 4.5):
        bridge.scrub("linesWidth", v)
    assert bridge.doc.item("ink").get("linesWidth", 1.5) == 1.5 and len(bridge.doc.history.changes) == n
    bridge.endScrub()
    assert [r["material"] for r in link.link.sent] == [{"id": "ink", "props": {"linesWidth": v}} for v in (2.0, 3.0, 4.5)]
    assert bridge.doc.item("ink")["linesWidth"] == 4.5 and len(bridge.doc.history.changes) == n + 1


def test_the_inline_rows_send_colours_linear(bridge):
    bridge.select("case")
    mats = bridge._mats
    mats._refresh()
    link = bridge.viewport = SimpleNamespace(link=Link(), look="quick")
    mats.beginScrub("linesColor")
    mats.scrub("linesColor", "#ff8000")
    mats.endScrub()
    assert link.link.sent[-1]["material"]["props"]["linesColor"] == pytest.approx(linear("#ff8000"))
    assert bridge.doc.item("ink")["linesColor"] == "#ff8000"


def test_the_final_look_previews_in_the_document(bridge):
    bridge.select("ink")
    link = bridge.viewport = SimpleNamespace(link=Link(), look="final")
    bridge.beginScrub("linesWidth")
    bridge.scrub("linesWidth", 2.0)
    bridge.endScrub()
    assert link.link.sent == [] and bridge.doc.item("ink")["linesWidth"] == 2.0
