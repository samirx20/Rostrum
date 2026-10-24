"""What would break silently in the render sheet: Quality there is the shot's own setting (one undo step) and the time
follows it at once from the kept measurement, with no new probe; Render uses exactly the settings the time was for.
No viewport, no real engine (the measurement is planted in a scratch cache)."""
import json
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_core.cache import Cache  # noqa: E402
from rostrum3d import estimate_job  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.export3d import Export3D  # noqa: E402
from screen3d.files_3d import FILES_3D  # noqa: E402

M = {"frame": 0, "samples": 128, "load_ms": 2000.0, "warmup_ms": 1000.0, "fixed_ms": 100.0, "per_px_ms": 0.002,
     "per_px_sample_ms": 0.00001, "probe": {"size": [480, 270], "ms": [900, 400]}, "gpu_busy": ""}


class NoEngine:
    proc, exe = None, Path(__file__)              # a stand-in build: part of the probe's key

    def __init__(self):
        raise AssertionError("the sheet started a probe; the kept measurement should have answered")


def test_quality_in_the_sheet_is_the_shots_and_rescales_at_once(tmp_path, monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(estimate_job, "CACHE", Cache(tmp_path / "cache"))
    folder = tmp_path / "Untitled scene"
    doc = FILES_3D.blank(folder)
    b = Bridge3D(Document.open(folder, doc.item_id, doc.kind), viewport=None)
    b.setPage("animate")
    ex = Export3D(b, make_engine=NoEngine)
    scene, info, s, _ = ex.plan_now()

    def plant(out):
        (out / "probe.json").write_text(json.dumps(M), encoding="utf-8")
        (out / "probe.png").write_bytes(b"")
    estimate_job.CACHE.put(estimate_job.KIND, estimate_job.probe_key(scene, s, NoEngine.exe), plant)

    ex.openFor()
    est = ex.estimate
    assert est.state == "ready" and est.text.startswith("About") and ex.choice == "shot"
    good = est.seconds
    ex.setShot("renderQuality", "draft")
    assert ex._shot()["renderQuality"] == "draft" and est.state == "ready" and est.seconds < good   # at once, no probe
    assert b.undoLabel                                                                                 # one step in the history
    plan = ex.begin(None, False)
    assert plan["cycles"]["samples"] == 32 and plan["size"] == (s["width"], s["height"])               # what the time was for
    b.close()
