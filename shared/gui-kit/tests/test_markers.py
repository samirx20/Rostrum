"""The ruler's marker edits are the shared marker operations: recorded with the person's name in the project's
marker history (what agents see through edit_markers), and a refused one is reported, not swallowed."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from rostrum_core import Who
from rostrum_core.markers import listing, open_markers

from rostrum_gui.markers import MarkerWatch


def test_ruler_edits_are_marker_operations(tmp_path):
    _app = QCoreApplication.instance() or QCoreApplication([])
    failed = []
    w = MarkerWatch(tmp_path, who=Who.person("sam"), fail=failed.append, owner="2d")
    a = w.add(1.0)
    b = w.add(2.0)
    assert [m["name"] for m in w.rows()] == ["Marker 1", "Marker 2"]
    assert w.rename(a, "logo lands") and w.move(b, 3.5)
    assert not w.rename(b, "Logo Lands") and failed          # names must differ: refused loudly
    assert w.remove(a)
    assert [(m["name"], m["at"]) for m in listing(tmp_path)] == [("Marker 2", 3.5)]
    assert [str(c.who) for c in open_markers(tmp_path).history.changes] == ["person:sam"] * 5
    w.close()
