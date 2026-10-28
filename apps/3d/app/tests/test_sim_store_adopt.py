"""A fall computed by another project (same set-up, so the shared result store has it) shows Stored in this one; moving
a body then reads "Out of date" with the old fall still shown, never "Not computed". The row has to record the stored
result as the shot's own the moment it sees it (SimJob.refresh -> adopt), or the shot has nothing to call out of date."""
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

HERE = Path(__file__).resolve()
sys.path[:0] = [str(HERE.parents[1]), str(HERE.parents[2] / "python" / "tests")]
from rostrum_core import Document, Who  # noqa: E402
from rostrum_core.cache import CACHE  # noqa: E402
from rostrum3d import KIND, run_source  # noqa: E402
from rostrum3d.sim import ops as sim_ops  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.files_3d import FILES_3D  # noqa: E402
from test_sim import SRC, FakeEngine  # noqa: E402


def test_a_result_from_the_shared_store_reads_out_of_date_after_a_move(tmp_path, monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    sim_ops.use_engine_factory(FakeEngine)
    try:
        other = Document.new(KIND)                     # another project computes this set-up: it is in the store
        other.run_script("s.py", run_source(SRC, "s.py"))
        other.apply([{"op": "sim.run", "target": ["drop"]}], Who.person())

        doc = FILES_3D.blank(tmp_path / "Mine")
        b = Bridge3D(Document.open(tmp_path / "Mine", doc.item_id, doc.kind), viewport=None)
        b.doc.run_script("s.py", run_source(SRC, "s.py"))
        b.shot_id = "drop"
        b.sim.refresh()
        assert b.sim.state == "stored"                          # from the store, this project never ran it
        for _ in range(5):
            QCoreApplication.processEvents()                    # the row records it (a zero-length timer)
        b.doc.apply([{"op": "mesh.set", "target": ["bowl"], "args": {"y": -0.5}}], Who.person())
        b.sim.refresh()
        assert b.sim.state == "out of date", b.sim.state
        b.close()
    finally:
        CACHE.settle()
        sim_ops.use_engine_factory(None)
