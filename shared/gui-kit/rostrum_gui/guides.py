"""An app's guides as Help-menu entries (TopBar `helpEntries`, above "About and licences"), and the guides drawer's
file reading and search (GuidesDrawer.qml, as the `guidePages` context property every window gets from `start`).

    entries(Path(__file__).parents[1] / "guides", [("first-song.md", "Making your first song"), …])

Or, without the list, from the guides themselves: `entries(folder)` reads each guide's front matter, a first block
between two `---` lines (the guide's own words in the guide's own file; the viewer and the agents' guide tool never show it):

    ---
    help: Making your first song
    order: 1
    ---

Help lists the guides that have `help:` (the label), by `order:` (a number; ties by file name). A folder with none,
a guide without a number `order:`, or two with the same label fails loudly at start. The menu is the same as the list's.

Each entry is {value: the file's file:// address, label}; picking one opens it in the app's own guide viewer.
The guides folder is the app's own (the installer copies apps/<app>/guides). A listed file that isn't there fails
loudly at start, so a renamed guide can't leave a dead menu entry.
"""
from __future__ import annotations

import re
from pathlib import Path

from rostrum_core.mcp.guides import split_front
from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, QUrl, Slot
from PySide6.QtGui import QImageReader, QTextBlockFormat, QTextCursor, QTextDocument

LINE_HEIGHT = 125      # % for lines of text; a line holding a picture keeps its own height (no blank band under it)
LIST_INDENT = 40      # px: Qt's indent of a list level; a picture inside a list item has that much less room
PICTURE_WIDTH = 720    # px: the default text column; the drawer passes its own (readAt), wider pictures fit it


def listed(folder: Path) -> list[tuple[str, str]]:
    """[(file, label)] for the guides whose front matter says `help:`, in `order:`."""
    found = []
    for f in sorted(Path(folder).glob("*.md")):
        meta = split_front(f.read_text(encoding="utf-8"))[0]
        if "help" in meta:
            if not meta.get("order", "").isdigit():
                raise ValueError(f"guide {f} says help: but has no number order: in its front matter")
            found.append((int(meta["order"]), f.name, meta["help"]))
    labels = [label for _, _, label in found]
    if not found or len(set(labels)) != len(labels):
        raise ValueError(f"guides in {folder}: " + ("none says help: in its front matter" if not found else "two share a Help label"))
    return [(name, label) for _, name, label in sorted(found)]


def entries(folder: Path, pages: list[tuple[str, str]] | None = None) -> list[dict]:
    pages = listed(folder) if pages is None else pages
    missing = [f for f, _ in pages if not (folder / f).is_file()]
    if missing:
        raise FileNotFoundError(f"guides missing from {folder}: {', '.join(missing)}")
    return [{"value": QUrl.fromLocalFile(str(folder / f)).toString(), "label": label} for f, label in pages]


def open_named(win, file: str):
    """A scripted step: open Help's guide `file` (e.g. "first-song.md") in the viewer; one not in Help fails loudly."""
    if not QMetaObject.invokeMethod(win, "openGuideNamed", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", file)):
        raise ValueError(f"guide {file!r} is not in this app's Help menu")
    if not win.property("guidesOpen"):    # a state that names the guide must show it, never another screen with no fault
        raise RuntimeError(f"guide {file!r} did not open: the guides drawer is not showing")


def page_html(markdown: str, folder: Path | None = None, width: int = PICTURE_WIDTH) -> str:
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
            _fit_pictures(block, folder, width)
        block = block.next()
    return re.sub(r'<body style="[^"]*">', "<body>", doc.toHtml(), count=1)


def _fit_pictures(block, folder: Path, width: int = PICTURE_WIDTH):
    """A picture wider than the viewer (a full-window screenshot) is shown at the viewer's width, never cut: less the
    indent it sits at (a picture in a list item)."""
    lst = block.textList()
    width -= LIST_INDENT * (lst.format().indent() if lst is not None else block.blockFormat().indent())
    for f in list(_fragments(block)):
        fmt = f.charFormat().toImageFormat()
        size = QImageReader(str(folder / fmt.name())).size()
        if size.width() > width:
            fmt.setWidth(width)
            fmt.setHeight(size.height() * width / size.width())
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
        return self.readAt(url, PICTURE_WIDTH)

    @Slot(str, int, result=str)
    def readAt(self, url: str, width: int) -> str:
        """A guide as rich text, its pictures no wider than `width` (the drawer's text column)."""
        path = Path(QUrl(url).toLocalFile())
        try:
            return page_html(split_front(path.read_text(encoding="utf-8"))[1], path.parent, max(80, width))
        except OSError as e:                      # shown in the viewer, never an empty page
            return page_html(f"# This guide could not be opened\n\n`{path}`\n\n{e.strerror or e}")

    @Slot("QVariantList", str, result="QVariantList")
    def search(self, entries, query: str) -> list:
        """The guides whose title or text holds every word of `query` (any case), each with the first line that
        does ({value, label, line}); every guide (line "") for an empty query."""
        words, out = query.lower().split(), []
        for e in entries:
            if not str(e.get("value", "")).lower().endswith(".md"):
                continue
            try:
                text = split_front(Path(QUrl(e["value"]).toLocalFile()).read_text(encoding="utf-8"))[1] if words else ""
            except OSError:
                text = ""
            if all(w in f'{e["label"]} {text}'.lower() for w in words):
                hit = (ln.strip(" #*->") for ln in text.splitlines() if any(w in ln.lower() for w in words))
                out.append({**e, "line": next(hit, "")[:120]})
        return out

    @Slot(str, str, result=str)
    def resolve(self, base: str, link: str) -> str:
        return QUrl(base).resolved(QUrl(link)).toString()
