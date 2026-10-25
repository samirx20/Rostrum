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
    bridge.select("card")                       # each item's own steps (many._by_item): the title's are not the card's
    assert bridge.lastChanged() == {}


def test_a_kinds_rows_come_back_as_the_document_is_now(bridge):
    """Each kind keeps its own list of rows (row_pages.py); one shown again has today's values, not its last ones."""
    bridge.select("title")
    text_rows = bridge.model.current
    bridge.select("card")
    assert bridge.model.current is not text_rows
    bridge.doc.apply([bridge.edit_call("title", "x", 123)], Who.agent("claude-code"), label="Moved title")
    bridge.select("title")
    assert bridge.model.current is text_rows
    assert next(r for r in text_rows.rows if r["id"] == "x")["value"] == 123
