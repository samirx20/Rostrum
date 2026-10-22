"""What the Mixer must keep doing: a fader drag is one undo step. Pure model level (no window), a few milliseconds."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, Signal
from rostrum_core import Document, Who
from rostrum_gui import DocBridge
from rostrum_sound import KIND, run_source


SRC = 'a = track("pad", builtIn="warmPad")\nb = track("keys", sfz="C:/x/Piano.sfz")\n'


class Bridge(DocBridge):
    renderChanged = Signal()
    lastRender = {}


def setup():
    QCoreApplication.instance() or QCoreApplication([])
    doc = Document.new(KIND)
    doc.run_script("t.py", run_source(SRC, "t.py"), Who.script("t.py"))
    return doc, Bridge(doc)


def test_fader_drag_is_one_undo_step():
    doc, bridge = setup()
    before = len(doc.history.changes)
    bridge.select("pad")
    bridge.beginScrub("volume")
    for v in (0.5, 0.7, 0.9):
        bridge.scrub("volume", v)
    bridge.endScrub()
    assert len(doc.history.changes) == before + 1 and doc.item("pad")["volume"] == 0.9
    bridge.undo()
    assert doc.item("pad")["volume"] == 0.85
