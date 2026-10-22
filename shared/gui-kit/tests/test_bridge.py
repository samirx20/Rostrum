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


def test_rows_by_importance_never_show_what_does_not_apply(bridge):
    """Opt-in only (the More row stays for every other bridge); a search or an opened group never brings back a
    setting that doesn't apply now, and open groups outlive a selection."""
    assert "more" in [r["id"] for r in bridge.model.rows]
    class Sectioned(DocBridge):
        sections = True
    b = Sectioned(toy.sample())
    b.select("cam_1")
    assert "more" not in [r["id"] for r in b.model.rows] and "shutter" not in b.shown()[0]
    b.setSearch("aper")                              # Aperture applies only with depth of field on
    assert b.shown()[0] == [] and b.nothingFound
    b.setValue("dof", True)
    assert b.shown()[0] == ["aperture"]
    b.setSearch("")
    b.toggleGroup("Shutter")
    b.select("cam_1")
    assert "motionBlur" in b.shown()[0] and "shutter" not in b.shown()[0]
    assert b.revealField("sensor") and "sensor" in b.shown()[0]


def test_an_app_cannot_overwrite_the_kits_names():
    """S24: the kit's `_opened` silently replaced Rostrum2D's. A kit name redefined or set by an app now fails loudly."""
    _app = QCoreApplication.instance() or QCoreApplication([])
    class Clash(DocBridge):
        def _refresh(self):
            pass
    with pytest.raises(TypeError, match="_refresh"):
        Clash(toy.sample())
    b = DocBridge(toy.sample())
    with pytest.raises(AttributeError):
        b.model = None
