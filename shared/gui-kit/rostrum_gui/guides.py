"""An app's guides as Help-menu entries (TopBar `helpEntries`, above "About and licences"), and the guide viewer's
file reading (GuideDialog.qml, as the `guidePages` context property every window gets from `start`).

    entries(Path(__file__).parents[1] / "guides", [("first-song.md", "Making your first song"), …])

Each entry is {value: the file's file:// address, label}; picking one opens it in the app's own guide viewer.
The guides folder is the app's own (the installer copies apps/<app>/guides). A listed file that isn't there fails
loudly at start, so a renamed guide can't leave a dead menu entry.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, QUrl, Slot


def entries(folder: Path, pages: list[tuple[str, str]]) -> list[dict]:
    missing = [f for f, _ in pages if not (folder / f).is_file()]
    if missing:
        raise FileNotFoundError(f"guides missing from {folder}: {', '.join(missing)}")
    return [{"value": QUrl.fromLocalFile(str(folder / f)).toString(), "label": label} for f, label in pages]


def open_named(win, file: str):
    """A scripted step: open Help's guide `file` (e.g. "first-song.md") in the viewer; one not in Help fails loudly."""
    if not QMetaObject.invokeMethod(win, "openGuideNamed", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", file)):
        raise ValueError(f"guide {file!r} is not in this app's Help menu")


class GuidePages(QObject):
    """What the viewer can't do in QML: read a guide's Markdown, and turn a link in it into a full address."""

    @Slot(str, result=str)
    def read(self, url: str) -> str:
        path = Path(QUrl(url).toLocalFile())
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:                      # shown in the viewer, never an empty page
            return f"# This guide could not be opened\n\n`{path}`\n\n{e.strerror or e}"

    @Slot(str, str, result=str)
    def resolve(self, base: str, link: str) -> str:
        return QUrl(base).resolved(QUrl(link)).toString()
