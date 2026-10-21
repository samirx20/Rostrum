"""What the Instruments and Mix pages must keep doing: a card's controls follow the data (valid_when), and a
fader drag is one undo step. Pure model level (no window), a few milliseconds."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, Signal
from rostrum_core import Document, Who
from rostrum_gui import DocBridge
from rostrum_sound import KIND, run_source

from screensound.instruments import InstrumentsPage

SRC = 'a = track("pad", builtIn="warmPad")\nb = track("keys", sfz="C:/x/Piano.sfz")\n'


class Bridge(DocBridge):
    renderChanged = Signal()
    lastRender = {}


def setup():
    QCoreApplication.instance() or QCoreApplication([])
    doc = Document.new(KIND)
    doc.run_script("t.py", run_source(SRC, "t.py"), Who.script("t.py"))
    return doc, Bridge(doc)


def shown(page, track_id):
    card = next(r for r in page.cards.rows if r["id"] == track_id)
    return [r["id"] for r in card["controls"].rows if r["row"] == "param" and r["valid"]], card


def test_card_controls_follow_the_instrument():
    doc, bridge = setup()
    page = InstrumentsPage(bridge)
    assert shown(page, "pad")[0] == ["instrument", "builtIn"]
    # one change; (picking "kit" alone is refused: the document needs its kit value too, see the report)
    doc.apply([{"op": "track.set", "target": ["pad"], "args": {"instrument": "kit", "kit": "synth"}}], Who.person("sam"))
    ids, card = shown(page, "pad")
    assert "kit" in ids and "builtIn" not in ids
    assert card["what"].startswith("Drum kit")


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
