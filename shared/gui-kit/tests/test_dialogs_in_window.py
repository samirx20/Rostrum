"""Every file and folder dialog opens inside its window (popupType: T.Popup.Item). Qt 6.8+ makes a Qt Quick dialog a
window of its own by default: in a check window kept behind the person's work it drew nowhere a grab or a click could
reach, so a script could not choose a file (critic 2d-final: Add a song from RostrumSound…). A dialog added without it
breaks that silently; this reads the QML of every app and the kit."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIALOG = re.compile(r"\b(FileDialog|FolderDialog)\s*\{")


def test_every_file_dialog_stays_inside_its_window():
    missing, seen = [], 0
    apps = [*ROOT.glob("apps/2d/*/qml/**/*.qml"), *ROOT.glob("apps/sound/*/qml/**/*.qml")]   # 3D: its team adds the line
    for qml in [*apps, *ROOT.glob("shared/gui-kit/qml/**/*.qml")]:
        if any(part in ("build", "target") for part in qml.parts):
            continue
        text = qml.read_text(encoding="utf-8")
        for m in DIALOG.finditer(text):
            seen += 1
            head = text[m.end():m.end() + 400]
            if "popupType: T.Popup.Item" not in head:
                missing.append(f"{qml.relative_to(ROOT)}:{text.count(chr(10), 0, m.start()) + 1}")
    assert seen >= 10
    assert not missing, "dialogs that would open as their own window: " + ", ".join(missing)
