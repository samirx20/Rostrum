"""An app's guides as Help-menu entries (TopBar `helpEntries`, above "About and licences").

    entries(Path(__file__).parents[1] / "guides", [("first-song.md", "Making your first song"), …])

Each entry is {value: the file's file:// address, label}; picking one opens the file in the computer's own viewer.
The guides folder is the app's own (the installer copies apps/<app>/guides). A listed file that isn't there fails
loudly at start, so a renamed guide can't leave a dead menu entry.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl


def entries(folder: Path, pages: list[tuple[str, str]]) -> list[dict]:
    missing = [f for f, _ in pages if not (folder / f).is_file()]
    if missing:
        raise FileNotFoundError(f"guides missing from {folder}: {', '.join(missing)}")
    return [{"value": QUrl.fromLocalFile(str(folder / f)).toString(), "label": label} for f, label in pages]
