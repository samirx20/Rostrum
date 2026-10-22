"""The settings panel's extra lines: narrowing a mixed selection is not a change; "Last changed by" names who."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication
from rostrum_core import Who, toy

from rostrum_gui import DocBridge


@pytest.fixture
def bridge():
    _app = QCoreApplication.instance() or QCoreApplication([])
    return DocBridge(toy.sample())


def test_narrowing_keeps_the_kind_and_is_no_undo_step(bridge):
    bridge.selectMany(["card", "title", "key"])
    assert [(n["kind"], n["label"]) for n in bridge.narrowLines()] == [("rect", "1 rect"), ("text", "1 text"), ("light", "1 light")]
    bridge.narrowTo("text")
    assert bridge.selection == ["title"] and bridge.narrowLines() == []
    assert bridge.doc.history.changes == []


def test_last_changed_names_the_author_and_follows_undo(bridge):
    bridge.select("title")
    assert bridge.lastChanged() == {}
    bridge.doc.apply([bridge.edit_call("title", "x", 5)], Who.agent("claude-code"), label="Moved title", session="s1")
    got = bridge.lastChanged()
    assert (got["who"], got["label"], got["session"], got["ago"]) == ("Claude", "Moved title", "s1", "just now")
    bridge.setValue("x", 9)
    assert bridge.lastChanged()["who"] == "You"
    bridge.undo()
    assert bridge.lastChanged()["who"] == "Claude"
