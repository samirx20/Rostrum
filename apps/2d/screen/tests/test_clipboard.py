"""Copy then paste gives the same layers under new ids (keys and effects included, a matte between them following
along), one change that Undo takes back; Cut is one change too."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who  # noqa: E402
from rostrum_core.tree import walk  # noqa: E402
from rostrum_gui import DocBridge  # noqa: E402
from rostrum2d import KIND  # noqa: E402
from screen2d.clipboard import ClipboardSlots  # noqa: E402


class Bridge(ClipboardSlots, DocBridge):
    def __init__(self, doc):
        self.comp_id = "film"
        super().__init__(doc)


def test_copy_paste_new_ids_same_layers_and_undo():
    QGuiApplication.instance() or QGuiApplication([])
    doc = Document.new(KIND)
    sam = Who.person("sam")
    doc.apply([{"op": "comp.add", "args": {"id": "film", "fps": 10, "duration": 5}},
               {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "card"}},
               {"op": "layer.add", "target": "film", "args": {"type": "text", "id": "title"}},
               {"op": "text.set", "target": "title", "args": {"body": "card", "matte": "card"}},
               {"op": "key.add", "target": "card", "args": {"prop": "x", "t": 1, "v": 300}}], sam)
    b = Bridge(doc)
    b.selectMany(["card", "title"])
    n = len(doc.history.changes)
    assert b.copyLayers() and len(doc.history.changes) == n           # copying changes nothing
    assert b.pasteLayers()
    assert len(doc.history.changes) == n + 1
    pasted = b.selection
    assert len(pasted) == 2 and not set(pasted) & {"card", "title"}
    old, new = (sorted((d for i in ids for d in walk(doc.item(i), KIND.lists)), key=lambda d: d["type"]) for ids in
                (["card", "title"], pasted))
    assert len(old) == len(new) and {d["id"] for d in old}.isdisjoint(d["id"] for d in new)   # keys came along
    text = next(d for d in new if d["type"] == "text")
    assert text["body"] == "card" and text["matte"] in pasted and text["matte"] != "card"     # words stay, links follow
    b.undo()
    assert not any(doc.has(i) for i in pasted)
    b.selectMany(["card"])
    m = len(doc.history.changes)
    assert b.cutLayers() and not doc.has("card") and len(doc.history.changes) == m + 1
    b.undo()
    assert doc.has("card")
