"""The Import panel's background job: the slow part runs on a worker, the ONE change (one undo step) is made on the GUI
thread; a cancel changes nothing; an error changes nothing and says so."""
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who  # noqa: E402
from rostrum2d import KIND  # noqa: E402
from screen2d.importer import Importer  # noqa: E402

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="#102030"/>' \
      '<path d="M10 10 L 90 10 L 50 80 Z" fill="#ff0000"/></svg>'


class Stub(QObject):
    who, comp_id, status = Who.agent("test"), "c", ""

    def __init__(self, folder):
        super().__init__()
        self.doc = Document.new(KIND, folder=str(folder), item="t")
        self.doc.apply([{"op": "comp.add", "args": {"id": "c", "width": 1920, "height": 1080}}], self.who)
        self.applied_on = []
        real = self.doc.apply
        self.doc.apply = lambda *a, **k: (self.applied_on.append(threading.current_thread()), real(*a, **k))[1]

    def _set_status(self, s):
        self.status = s

    def _fail(self, s):
        self.status = s

    def select(self, _):
        pass


def make(tmp_path):
    QCoreApplication.instance() or QCoreApplication([])
    (tmp_path / "t.svg").write_text(SVG, encoding="utf-8")
    b = Stub(tmp_path / "doc")
    imp = Importer(b)
    imp.setFile(str(tmp_path / "t.svg"))
    return b, imp


def test_import_applies_once_on_the_gui_thread_and_fits(tmp_path):
    b, imp = make(tmp_path)
    imp.run()
    assert imp.wait(30) and imp.state == "done"
    assert b.applied_on == [threading.main_thread()]
    (_frame, root) = b.doc.item("c")["layers"]                       # one group = the picture's content box (400x300), own size, centred
    assert (root.get("scale", 1.0), root["x"], root["y"]) == (1.0, 760, 390)
    b.doc.undo(b.who)
    assert [l["type"] for l in b.doc.item("c")["layers"]] == ["camera"]     # one undo step: only the scene's frame


def test_cancel_and_errors_change_nothing(tmp_path):
    b, imp = make(tmp_path)
    imp._state = "running"
    imp.job.cancelled = True                                   # asked to stop just as the plan came back: still nothing applied
    plan = {"name": "x", "kind": "svg", "calls": [{"op": "layer.add", "target": ["c"], "args": {"type": "shape", "id": "s"}}],
            "report": [], "into": "c", "label": "x"}
    imp._finish(plan, "", False)
    assert imp.state == "cancelled" and "nothing imported" in imp.note and [l["type"] for l in b.doc.item("c")["layers"]] == ["camera"]
    imp.setFile(str(tmp_path / "missing.svg"))
    imp.run()
    assert imp.wait(30) and imp.state == "failed" and "no file" in imp.note and [l["type"] for l in b.doc.item("c")["layers"]] == ["camera"]
