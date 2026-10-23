"""Ctrl / Shift / Alt are read from the event (qml/Mods.js). `Qt.application` has no keyboardModifiers in this Qt: the
read is silently nothing, so a Ctrl+drag lasso became a plain stroke. No screen in the repo may read it again."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def test_no_global_modifier_reads():
    bad = [str(p.relative_to(REPO)) for p in REPO.glob("**/*.qml")
           if "build" not in p.parts and "keyboardModifiers" in p.read_text(encoding="utf-8", errors="ignore")]
    assert not bad, f"read the modifiers from the event (Mods.js), not a global: {bad}"
