"""No popup silently stops the window's keys, and every one closes on the window's one Esc. A plain QQC.Popup that closes on
Esc (Qt's default) stops EVERY window shortcut while it is open (Ctrl+Z, Space ... dead), and its Esc works only while it has
the keyboard. So every menu, dropdown, flyout, panel and dialog (modal ones too) is a SmallPopup (OpenPopups.qml: AppShell's
Esc closes the newest); a plain QQC.Popup is only a passive line that never closes by itself (`NoAutoClose`: a hover tip)."""
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
                if re.search(r"\bmodal:\s*true", own) or "NoAutoClose" not in own:
                    bad.append(f"{f.relative_to(ROOT)}:{text[:m.start()].count(chr(10)) + 1}")
    assert not bad, ("a plain QQC.Popup would stop the window's keys while open, and Esc would not reach it; make it a "
                     "SmallPopup (a dialog too: SmallPopup { modal: true }): " + ", ".join(bad))


def test_no_popup_closes_on_esc_by_qt():
    """Qt's own Esc close (CloseOnEscape) nowhere: it stops every window key while open, works only while the popup has the
    keyboard, and would answer the same Esc as the window's one (AppShell), which then does nothing."""
    bad = []
    for folder in FOLDERS:
        for f in folder.rglob("*.qml"):
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines()):
                if "CloseOnEscape" in line and not line.strip().startswith("//"):
                    bad.append(f"{f.relative_to(ROOT)}:{n + 1}")
    assert not bad, "CloseOnEscape on a popup (make it a SmallPopup: the window's one Esc closes it): " + ", ".join(bad)
