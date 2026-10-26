"""An item's settings rows borrowed from an alike item's (row_memo.borrow) show what its own values decide: a camera
with depth of field on shows Focus distance, whichever camera's rows it borrowed. The first try at borrowing copied
the rows' visibility from a stale entry and lost Focus distance with no error anywhere."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication
from rostrum_core import toy

from rostrum_gui import DocBridge


@pytest.fixture
def b():
    _app = QCoreApplication.instance() or QCoreApplication([])
    b = DocBridge(toy.sample())
    for _ in range(2):
        b.doc.apply([{"op": "layer.add", "target": [], "args": {"type": "camera"}}], b.who)
    real, b.borrowed = b._kit.memo.borrow, []

    def borrow(item_id, *a, **k):
        e = real(item_id, *a, **k)
        if e is not None:
            b.borrowed.append(item_id)
        return e
    b._kit.memo.borrow = borrow
    return b


def _shows(b, item_id):
    return {r["id"] for r in b._kit.memo.entries[item_id].rows if r["row"] == "param" and r["valid"]}


def test_focus_distance_follows_each_cameras_own_depth_of_field(b):
    cams = [i["id"] for i in b.doc.items() if i["type"] == "camera"]
    assert len(cams) == 3
    b.selectMany(cams)
    assert set(b.borrowed) == set(cams[1:])                 # alike: the 2nd and 3rd borrow the 1st's rows
    assert not any("focusDistance" in _shows(b, c) for c in cams)

    b.select(cams[1])
    b.setValue("dof", True)                                 # its kept entry's visibility is stale now
    assert "focusDistance" in b.shown()[0]
    b.selectMany(cams)
    assert "focusDistance" in _shows(b, cams[1]) and "focusDistance" not in _shows(b, cams[2])

    b.select(cams[2])
    b.setValue("dof", True)
    b._kit.memo.clear()                                     # (as an add or delete does)
    b.borrowed.clear()
    b.selectMany([cams[0], cams[1], cams[2]])
    assert b.borrowed == [cams[2]]                          # borrowed from the one with depth of field on
    assert "focusDistance" in _shows(b, cams[2]) and "focusDistance" not in _shows(b, cams[0])
    b.select(cams[2])
    assert "focusDistance" in b.shown()[0]
    b.select(cams[0])
    assert "focusDistance" not in b.shown()[0]
