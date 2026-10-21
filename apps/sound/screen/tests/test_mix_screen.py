"""What the Mix page's new controls must keep doing: picking a delivery target is ONE history step that sets both
numbers; a duck is added and edited by operations (one step each); a plug-in's own Bypass is not offered as a setting.
Model level (no window), milliseconds."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication
from rostrum_core import Document, Who
from rostrum_gui import DocBridge
from rostrum_sound import KIND, run_source

from screensound import delivery, plugin_rows
from screensound.ducks import DuckHub

SRC = 'a = track("pad", builtIn="warmPad")\nb = track("voice", builtIn="warmPad")\n'


def setup():
    QCoreApplication.instance() or QCoreApplication([])
    doc = Document.new(KIND)
    doc.run_script("t.py", run_source(SRC, "t.py"), Who.script("t.py"))
    return doc, DocBridge(doc)


def test_delivery_target_is_one_step_with_both_numbers():
    doc, _ = setup()
    doc.apply([{"op": "master.set", "target": ["master"], "args": {"normalize": True}}], Who.person("sam"))   # the chooser shows only then
    before = len(doc.history.changes)
    doc.apply([delivery.call("ebu")], Who.person("sam"))
    m = doc.item("master")
    assert len(doc.history.changes) == before + 1
    assert (m["loudness"], m["truePeak"], delivery.key_of(m)) == (-23.0, -1.0, "ebu")


def test_verdict_passes_within_a_unit_and_under_the_ceiling():
    m = {"loudness": -14, "truePeak": -1}
    assert delivery.verdict(m, {"lufs": -14.6, "truePeak": -1.4})["ok"]
    miss = delivery.verdict(m, {"lufs": -11.0, "truePeak": 0.3})
    assert not miss["ok"] and "too loud" in miss["text"] and "over the ceiling" in miss["text"]


def test_duck_is_added_and_a_drag_is_one_step():
    doc, bridge = setup()
    hub = DuckHub(bridge)
    assert hub.add("pad", "voice") and hub.panel["under"] == [{"id": "voice", "label": "voice"}]
    before = len(doc.history.changes)
    hub.beginScrub("depth")
    for v in (0.6, 0.7, 0.8):
        hub.scrub("depth", v)
    hub.endScrub()
    assert len(doc.history.changes) == before + 1 and doc.item("pad.duck_1")["depth"] == 0.8
    assert "under" not in [r["id"] for r in hub.controls.rows]          # tracks have their own chips


def test_plugins_own_bypass_is_not_a_setting():
    rows = plugin_rows.layout([{"id": 1, "name": "Bypass", "min": 0, "max": 1}, {"id": 2, "name": "Mix", "min": 0, "max": 1}])
    assert [r["id"] for r in rows if r["row"] == "param"] == ["2"]
