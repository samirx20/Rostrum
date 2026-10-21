"""The bridge's promise to people: one edit or one whole scrub = one undo step, and Ctrl+Z puts it back."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication
from rostrum_core import toy

from rostrum_gui import DocBridge


@pytest.fixture
def bridge():
    _app = QCoreApplication.instance() or QCoreApplication([])
    b = DocBridge(toy.sample())
    b.select("cam_1")
    return b


def test_scrub_is_one_change_and_undo_reverts_it(bridge):
    doc = bridge.doc
    bridge.beginScrub("focal")
    for v in (52, 61, 70, 85):
        bridge.scrub("focal", v)
    bridge.endScrub()
    assert doc.item("cam_1")["focal"] == 85
    assert len(doc.history.changes) == 1
    bridge.undo()
    assert doc.item("cam_1")["focal"] == 50


def test_toggle_edit_is_one_change_and_shows_its_rows(bridge):
    bridge.setValue("dof", True)
    assert len(bridge.doc.history.changes) == 1
    assert "focusDistance" in bridge.shown()[0]     # the rows follow the document in place
    bridge.undo()
    assert bridge.doc.item("cam_1")["dof"] is False
    assert "focusDistance" not in bridge.shown()[0]
