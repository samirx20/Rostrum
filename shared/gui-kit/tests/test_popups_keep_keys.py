"""No popup silently stops the window's keys. A plain QQC.Popup that closes on Esc (Qt's default) stops EVERY window shortcut
while it is open (Ctrl+Z, Space ... dead). So every menu, dropdown, flyout and panel is a SmallPopup (OpenPopups.qml); a plain
QQC.Popup is only a dialog that blocks the window on purpose (`modal: true`) or a passive line that never closes by itself
(`NoAutoClose`: a hover tip)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLDERS = [ROOT / "shared" / "gui-kit" / "qml", ROOT / "apps" / "2d" / "screen" / "qml", ROOT / "apps" / "sound" / "screen" / "qml"]
POPUP = re.compile(r"^(\s*)QQC\.Popup\s*\{", re.M)


def _block(text: str, start: int) -> str:
    """The popup's own lines (to its closing brace), without the bodies of its children's blocks."""
    depth, i = 0, text.index("{", start)
    own = []
    for j in range(i, len(text)):
        c = text[j]
        depth += c == "{"
        depth -= c == "}"
        if depth == 1 or (depth == 2 and c == "{"):
            own.append(c)
        if depth == 0:
            break
    return "".join(own)


def test_every_popup_keeps_the_window_keys():
    bad = []
    for folder in FOLDERS:
        for f in folder.rglob("*.qml"):
            if f.name == "SmallPopup.qml":
                continue
            text = f.read_text(encoding="utf-8")
            for m in POPUP.finditer(text):
                own = _block(text, m.start())
                if not re.search(r"\bmodal:\s*true", own) and "NoAutoClose" not in own:
                    bad.append(f"{f.relative_to(ROOT)}:{text[:m.start()].count(chr(10)) + 1}")
    assert not bad, "a plain QQC.Popup would stop the window's keys while open; make it a SmallPopup: " + ", ".join(bad)


def test_only_a_dialog_closes_on_esc_by_qt():
    """Qt's own Esc close (CloseOnEscape) only on a modal dialog: anywhere else it stops every window key while open."""
    bad = []
    for folder in FOLDERS:
        for f in folder.rglob("*.qml"):
            lines = f.read_text(encoding="utf-8").splitlines()
            for n, line in enumerate(lines):
                near = " ".join(lines[max(0, n - 8):n + 3])
                if "CloseOnEscape" in line and not re.search(r"\bmodal:\s*true", near):
                    bad.append(f"{f.relative_to(ROOT)}:{n + 1}")
    assert not bad, "CloseOnEscape on a popup that is not a modal dialog (use SmallPopup: its Esc keeps the window keys): " + ", ".join(bad)
