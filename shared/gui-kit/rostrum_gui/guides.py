"""An app's guides as Help-menu entries (TopBar `helpEntries`, above "About and licences"), and the guide viewer's
file reading (GuideDialog.qml, as the `guidePages` context property every window gets from `start`).

    entries(Path(__file__).parents[1] / "guides", [("first-song.md", "Making your first song"), …])

Each entry is {value: the file's file:// address, label}; picking one opens it in the app's own guide viewer.
The guides folder is the app's own (the installer copies apps/<app>/guides). A listed file that isn't there fails
loudly at start, so a renamed guide can't leave a dead menu entry.
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, QUrl, Slot
from PySide6.QtGui import QImageReader, QTextBlockFormat, QTextCursor, QTextDocument

LINE_HEIGHT = 125      # % for lines of text; a line holding a picture keeps its own height (no blank band under it)
PICTURE_WIDTH = 720    # px: the guide viewer's text column (820 less its margins); wider pictures are shown at this width


def entries(folder: Path, pages: list[tuple[str, str]]) -> list[dict]:
    missing = [f for f, _ in pages if not (folder / f).is_file()]
    if missing:
        raise FileNotFoundError(f"guides missing from {folder}: {', '.join(missing)}")
    return [{"value": QUrl.fromLocalFile(str(folder / f)).toString(), "label": label} for f, label in pages]


def open_named(win, file: str):
    """A scripted step: open Help's guide `file` (e.g. "first-song.md") in the viewer; one not in Help fails loudly."""
    if not QMetaObject.invokeMethod(win, "openGuideNamed", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", file)):
        raise ValueError(f"guide {file!r} is not in this app's Help menu")


def page_html(markdown: str, folder: Path | None = None) -> str:
    """A guide's Markdown as the viewer's rich text. Line spacing is set per paragraph, on text only: a Text's own
    lineHeight stretches every line by the same factor, so a 400 px picture got 100 px of blank space under it.
    The font is left to the viewer (its Text's font), not fixed by the document."""
    doc = QTextDocument()
    doc.setMarkdown(markdown)
    spaced = QTextBlockFormat()
    spaced.setLineHeight(LINE_HEIGHT, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
    block = doc.begin()
    while block.isValid():
        if not any(f.charFormat().isImageFormat() for f in _fragments(block)):
            QTextCursor(block).mergeBlockFormat(spaced)
        elif folder is not None:
            _fit_pictures(block, folder)
        block = block.next()
    return re.sub(r'<body style="[^"]*">', "<body>", doc.toHtml(), count=1)


def _fit_pictures(block, folder: Path):
    """A picture wider than the viewer (a full-window screenshot) is shown at the viewer's width, never cut."""
    for f in list(_fragments(block)):
        fmt = f.charFormat().toImageFormat()
        size = QImageReader(str(folder / fmt.name())).size()
        if size.width() > PICTURE_WIDTH:
            fmt.setWidth(PICTURE_WIDTH)
            fmt.setHeight(size.height() * PICTURE_WIDTH / size.width())
            cur = QTextCursor(block.document())
            cur.setPosition(f.position()); cur.setPosition(f.position() + f.length(), QTextCursor.MoveMode.KeepAnchor)
            cur.setCharFormat(fmt)


def _fragments(block):
    it = block.begin()
    while not it.atEnd():
        yield it.fragment()
        it += 1


class GuidePages(QObject):
    """What the viewer can't do in QML: read a guide (as rich text: page_html), and turn a link in it into a full
    address."""

    @Slot(str, result=str)
    def read(self, url: str) -> str:
        path = Path(QUrl(url).toLocalFile())
        try:
            return page_html(path.read_text(encoding="utf-8"), path.parent)
        except OSError as e:                      # shown in the viewer, never an empty page
            return page_html(f"# This guide could not be opened\n\n`{path}`\n\n{e.strerror or e}")

    @Slot(str, str, result=str)
    def resolve(self, base: str, link: str) -> str:
        return QUrl(base).resolved(QUrl(link)).toString()
