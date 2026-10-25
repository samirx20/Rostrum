"""The ruler's marker edits are the shared marker operations: recorded with the person's name in the project's
marker history (what agents see through edit_markers), and a refused one is reported, not swallowed."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from rostrum_core import Who
from rostrum_core.markers import edit, listing, open_markers

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


def test_screen_undo_takes_back_marker_edits_in_one_history(tmp_path):
    """One history per person across the document and the project's markers (AGENTS.md rule 3)."""
    from rostrum_core import toy
    from rostrum_gui import DocBridge
    _app = QCoreApplication.instance() or QCoreApplication([])
    b = DocBridge(toy.sample(), who=Who.person("sam"))
    w = MarkerWatch(tmp_path, who=b.who, owner="2d")
    b.join_history(w)
    b.select("cam_1")
    b.setValue("focal", 60)
    w.add(1.0)
    b.setValue("dof", True)
    assert b.historyCount == 3
    b.undo()
    assert b.doc.item("cam_1")["dof"] is False and len(w.rows()) == 1
    b.undo()
    assert w.rows() == [] and b.doc.item("cam_1")["focal"] == 60      # the marker edit, from the same button
    b.undo()
    assert b.doc.item("cam_1")["focal"] == 50
    b.redo(); b.redo()
    assert b.doc.item("cam_1")["focal"] == 60 and len(w.rows()) == 1   # redone in order, across both
    edit(tmp_path, [{"op": "marker.move", "target": [w.rows()[0]["id"]], "args": {"at": 2.0}}], Who.agent("claude"))
    w.refresh()
    assert b.status == "Claude: Move marker"                           # an agent's marker edit: who changed what
    w.close()


def test_a_change_asks_no_file_between_polls(tmp_path, monkeypatch):
    """A change and an Undo on a screen whose project has no markers yet look at no file: the marker document, its
    file's stamp and the ↶ ↷ labels are kept between the marker watch's polls (Sound asked 12 times per Undo)."""
    from rostrum_core import toy
    from rostrum_gui import DocBridge
    _app = QCoreApplication.instance() or QCoreApplication([])
    b = DocBridge(toy.sample(), who=Who.person("sam"))
    w = MarkerWatch(tmp_path, who=b.who, owner="2d")
    b.join_history(w)
    b.select("cam_1")
    asked, real = [], os.stat
    monkeypatch.setattr(os, "stat", lambda *a, **k: asked.append(str(a[0])) or real(*a, **k))
    b.setValue("focal", 60)
    b.undo()
    monkeypatch.undo()
    assert b.undoLabel == "" and b.redoLabel and b.historyCount == 0
    assert not asked, asked
    w.add(1.0)                                          # this process's own save: seen at once, no poll needed
    assert len(w.rows()) == 1 and b.historyCount == 1
    w.close()
