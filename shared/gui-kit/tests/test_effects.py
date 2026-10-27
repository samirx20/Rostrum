"""The Effects row only calls operations (one change each), and Reset is one set operation = one undo step."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))

import effects_demo
import pytest
from PySide6.QtCore import QCoreApplication

from rostrum_gui import DocBridge, effects


@pytest.fixture
def made():
    _app = QCoreApplication.instance() or QCoreApplication([])
    bridge = DocBridge(effects_demo.sample())
    bridge.select("card")
    return bridge, effects.attach(bridge, effects_demo.SPEC)


def test_add_and_remove_are_one_undoable_change_each(made):
    bridge, part = made
    assert part.add("shadow") and [g.id for g in part.groups] == ["blur_1", "glow_1", "shadow_1"]
    assert len(bridge.doc.history.changes) == 1 and all(g.open for g in part.groups)   # each shows its settings (not folded)
    assert part.remove("glow_1") and part.count == 2
    bridge.undo()
    bridge.undo()
    assert part.count == 2 and [g.id for g in part.groups] == ["blur_1", "glow_1"]


def test_row_absent_with_several_selected_or_a_kind_without_effects(made):
    bridge, part = made
    bridge.selectMany(["card", "plain"])
    assert not part.shown
    bridge.select("plain")
    assert part.shown and part.count == 0           # nothing added yet, but the + is there


def test_effect_edit_is_an_operation_on_the_effect(made):
    bridge, part = made
    part.groups[0].setValue("radius", 30)
    assert bridge.doc.item("blur_1")["radius"] == 30 and len(bridge.doc.history.changes) == 1


def test_reset_is_one_undo_step(made):
    """What right-click › Reset sends: the row's default through setValue."""
    bridge, _ = made
    row = next(r for r in bridge.model.rows if r["id"] == "radius")
    assert row["default"] == 8 and bridge.doc.item("card")["radius"] == 24
    bridge.setValue("radius", row["default"])
    assert bridge.doc.item("card")["radius"] == 8 and len(bridge.doc.history.changes) == 1
    bridge.undo()
    assert bridge.doc.item("card")["radius"] == 24
