"""What would break silently: Ctrl+V with nothing copied answers in the message line (critic r12 should-fix 6)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screensound import clipboard  # noqa: E402
from test_screen import bridge  # noqa: E402,F401


def test_paste_with_nothing_copied_says_so(bridge, monkeypatch):  # noqa: F811
    monkeypatch.setattr(bridge, "_board", {"items": [], "tracks": []}, raising=False)
    bridge.selectMany(["lead.n2000"])
    bridge.actions.key("paste")
    assert "Nothing copied yet" in bridge.status
