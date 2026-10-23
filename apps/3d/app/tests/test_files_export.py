"""What would break silently in Rostrum3D's file pieces: a new scene opens again whole (New, then Open); an export whose
engine fails is reported red in words, never "done", and writes no finished version. No viewport, no real engine."""
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_gui import docfiles  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.export3d import Export3D  # noqa: E402
from screen3d.files_3d import FILES_3D, resolve  # noqa: E402


class BrokenEngine:
    proc = None

    def ensure_scene(self, scene):
        raise RuntimeError("the engine would not start")

    def close(self):
        pass


def test_new_scene_opens_again_and_a_failed_export_says_so(tmp_path):
    QGuiApplication.instance() or QGuiApplication([])
    folder = tmp_path / "Untitled scene"
    doc = FILES_3D.blank(folder)
    again = docfiles.open_whole(FILES_3D, *resolve(folder))
    assert again.data == doc.data and again.data["shots"]
    b = Bridge3D(Document.open(folder, doc.item_id, doc.kind), viewport=None)
    ex = Export3D(b, make_engine=BrokenEngine)
    ex.request()
    assert ex.wait(30)
    assert ex.state == "failed" and "engine would not start" in ex.note and b.status.startswith("Error")
    assert not list((folder / "renders").glob("*/v???")) if (folder / "renders").exists() else True
    b.close()
