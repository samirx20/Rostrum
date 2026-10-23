"""A value typed in the Key block lands on the keys it was typed for, not on keys picked after (the kit's rule, see
shared/gui-kit/tests/test_typed_value.py); a key that is gone drops the value with a plain message."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rostrum_core.keys import keys_of  # noqa: E402
from screen2d.bridge2d import Bridge2D  # noqa: E402
from test_screen import FakeEngine, frames, Document, KIND, run_source, SRC  # noqa: E402,F401


@pytest.fixture
def bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(frames, "open_engine", FakeEngine)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    b = Bridge2D(doc)
    b.select("title")
    yield b
    b.close()


def _values(b):
    return [k["v"] for k in keys_of(b.doc.item("title"), "opacity")]


def test_typed_value_goes_to_the_key_it_was_typed_for(bridge):
    first, second = (k["id"] for k in keys_of(bridge.doc.item("title"), "opacity"))
    bridge._keys.click([first], "", [[first], [second]])
    bridge.keyBar.hold("value")                         # the caret went in
    bridge._keys.click([second], "", [[first], [second]])   # other keys picked before the value was entered
    bridge.keyBar.setValue(0.5)
    bridge.keyBar.release("value")
    assert _values(bridge) == [0.5, 1]
    assert len(bridge.doc.history.changes) == 1 + 1     # the script + one undo step


def test_a_gone_key_drops_the_typed_value_plainly(bridge):
    first = keys_of(bridge.doc.item("title"), "opacity")[0]["id"]
    bridge._keys.click([first], "", [[first]])
    bridge.keyBar.hold("value")
    bridge._keys.clear()
    bridge.doc.apply([{"op": "key.remove", "target": [first], "args": {}}], bridge.who)
    assert bridge.keyBar.setValue(0.5) is False
    assert _values(bridge) == [1]
