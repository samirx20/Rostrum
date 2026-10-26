"""What would break silently in the Render page's queue: a second render waits while the first runs, and cancelling
the running one ends its engine process and leaves nothing on disk (not even its `.partial`), with the row saying
"Render cancelled". A stand-in engine (python fake_core.py, a render that takes a minute); no graphics card."""
import os
import sys
import time
from pathlib import Path

from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, project  # noqa: E402
from rostrum3d.engine import Engine  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.files_3d import FILES_3D  # noqa: E402

FAKE = Path(__file__).resolve().parents[2] / "python" / "tests" / "fake_core.py"


def _until(test, what, s=20):
    t0 = time.monotonic()
    while not test():
        assert time.monotonic() - t0 < s, f"{what} did not happen in {s} s"
        time.sleep(0.05)


def test_cancel_leaves_nothing_and_says_so(tmp_path):
    QGuiApplication.instance() or QGuiApplication([])
    made = []

    def slow():
        made.append(Engine(sys.executable, {**os.environ, "FAKE_SLOW": "1"}, args=(str(FAKE), "serve")))
        return made[-1]

    folder = tmp_path / "Queue scene"
    doc = FILES_3D.blank(folder)
    b = Bridge3D(Document.open(folder, doc.item_id, doc.kind), viewport=None, render_engine=slow)
    q = b.queue
    first = q.call("render.queue.add", {"shot": "hero"})
    second = q.call("render.queue.add", {"shot": "hero"})
    _until(lambda: made and made[0].proc is not None and q.jobs.get(first).status == "running", "the first render starting")
    assert q.jobs.get(second).status == "queued"                       # one at a time: the second waits
    proc = made[0].proc
    q.call("render.queue.cancel", {"job": first})
    q.jobs.wait(first, 20)
    assert q.jobs.get(first).status == "cancelled"
    assert proc.poll() is not None                                     # its engine process was ended
    q.call("render.queue.cancel", {"job": second})
    q.jobs.wait(second, 20)
    q.refresh()
    rows = {r["id"]: r for r in q.rows}
    assert rows[first]["word"] == "Render cancelled" and rows[first]["status"] == "cancelled"
    assert project.renders(folder, doc.item_id) == []                  # nothing listed as a version
    left = sorted(d.name for d in (folder / "renders" / doc.item_id).iterdir())
    assert left == [], left                                            # its half-made .partial folder went too
    b.close()
