"""What would break silently in File > Save: the recovery copy must bring back the unsaved edits (history and all)
without touching the saved document, and Save must write the document and drop the recovery copy. No window."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who  # noqa: E402
from rostrum2d import KIND  # noqa: E402
from screen2d import projects  # noqa: E402

WHO = Who.person("sam")


def test_recovery_restores_unsaved_edits_and_save_clears_it(tmp_path):
    doc = projects.new_project("Promo", WHO, root=tmp_path)
    saved_text = (doc.folder / "docs" / "main.mtn").read_text(encoding="utf-8")
    doc.apply([{"op": "layer.add", "target": ["main"], "args": {"type": "shape", "id": "box"}}], WHO, label="Add shape")

    projects.write_recovery(doc)
    assert (doc.folder / "docs" / "main.mtn").read_text(encoding="utf-8") == saved_text   # the saved file is untouched
    assert projects.recovery_time(doc.folder, "main") is not None

    back = projects.open_recovery(doc.folder, "main")
    assert back.has("box") and back.folder == doc.folder
    assert len(back.history.changes) == len(doc.history.changes)                          # undo still reaches the edit
    assert not Document.open(doc.folder, "main", KIND).has("box")

    back.save()
    projects.clear_recovery(back.folder)
    assert projects.recovery_time(back.folder, "main") is None
    assert Document.open(doc.folder, "main", KIND).has("box")
