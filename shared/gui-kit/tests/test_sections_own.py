"""A kind's own group is always open, a changed group opens, the rest are names (sections.OWN, the kit's option)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))

from PySide6.QtCore import QCoreApplication

import groups_demo


def test_light_shows_own_and_changed_groups_open_and_the_rest_as_names():
    _app = QCoreApplication.instance() or QCoreApplication([])
    b = groups_demo.Bridge(groups_demo.sample())
    b.select("key")
    folds = {r["fold"]: r for r in b.model.rows if "fold" in r}
    assert [g for g, r in folds.items() if r["open"]] == ["Light", "Position"]
    names = next(r for r in b.model.rows if r["row"] == "folds")["names"]
    assert [n["group"] for n in names] == ["Spread", "Card", "Lights only", "Shadow"]
    b.toggleGroup("Light")                       # the own group never folds
    assert next(r for r in b.model.rows if r.get("fold") == "Light")["open"]
    b.toggleGroup("Card")
    assert next(r for r in b.model.rows if r.get("fold") == "Card")["open"]
