"""Rostrum2D's thin adapter to the kit's one file model (shared/gui-kit/FILES.md): a project is a folder with
`docs/<item>.mtn` (rostrum_core/storage.py); a new one holds one blank composition. Every window is live, so there is
no Save, no unsaved mark and no recovery copy: the kit's ProjectFiles does New, Open, Open recent, Duplicate, Save a
version, Show folder and the start screen. No Qt here except the picture the start screen shows.
"""
from __future__ import annotations

from pathlib import Path

from rostrum2d import KIND, settings
from rostrum_core import Document, RostrumError, Who, codes
from rostrum_gui.docfiles import AppFiles
from rostrum_paint import library

ITEM = "main"                                     # the item a new project's document gets
BLANK = {"id": "main", "name": "Main", "width": 1920, "height": 1080, "fps": 25, "duration": 10.0}
GUIDES = Path(__file__).resolve().parents[2] / "guides"


def blank(folder: Path | None) -> Document:
    """One blank composition (1920 × 1080, 25 fps, 10 s), saved in `folder` (None: in memory). It is the document's
    starting contents, not a change: a new project has nothing to undo."""
    doc = Document.new(KIND, folder=folder, item=ITEM if folder else None,
                       start=[{"op": "comp.add", "args": dict(BLANK)}])
    if folder:
        doc.save()
    return doc


def resolve(path) -> tuple[Path, str]:
    """A picked path -> (project folder, item): a docs/<item>.mtn file, or a project folder (its `main`, else its only
    2D document)."""
    p = Path(path)
    if p.is_file() and p.suffix == KIND.ext and p.parent.name == "docs":
        return p.parent.parent, p.stem
    if p.is_dir():
        docs = sorted((p / "docs").glob(f"*{KIND.ext}"))
        main = [d for d in docs if d.stem == ITEM]
        if main or len(docs) == 1:
            return p, (main or docs)[0].stem
        found = ", ".join(d.stem for d in docs) or "none"
        raise RostrumError(codes.BAD_ARGUMENT, "open", str(p), f"has no single 2D document to open (found: {found})",
                           hint=f"Pick the file in {p / 'docs'}. Nothing was changed.")
    raise RostrumError(codes.BAD_ARGUMENT, "open", str(p), f"is not a Rostrum2D project folder or {KIND.ext} file",
                       hint="Nothing was changed.")


def repoint(copy: Document, old, new) -> None:
    """Duplicate: image and video layers whose file sits inside the old project folder point into the copy (one
    change in the copy's history; the original is not touched)."""
    old, calls = Path(old).resolve(), []
    for it in copy.items():
        src = it.get("src")
        if it.get("type") in ("image", "video") and src:
            try:
                rel = Path(src).resolve().relative_to(old)
            except ValueError:
                continue
            calls.append({"op": f"{it['type']}.set", "target": [it["id"]], "args": {"src": str(Path(new) / rel)}})
    if calls:
        copy.apply(calls, Who.person("sam"), label="Imported files now in the copy")
        copy.save()


def save_into(doc: Document, folder, item: str = ITEM) -> Document:
    """The ONE place a scene with no project yet is first saved into a project folder: the document gets the folder, then
    every picture / video it keeps in the app's temporary store (what an import on an unsaved scene wrote) is copied into
    the project's media and its layers rewritten, as ONE change "Keep files in the project" in the history (undoable, and
    a re-run script never wipes it). Nothing in it is then "File outside the project". A scene with nothing in the store
    saves with no extra change."""
    from rostrum2d import media
    doc.folder, doc.item_id = Path(folder), item
    calls = media.keep_calls([i for i in doc.items() if i.get("type") in media.TYPES and i.get("src")], folder)
    if calls:
        doc.apply(calls, Who.person("sam"), label="Keep files in the project")
    doc.save()
    return doc


def open_doc(folder, item):
    library.use_project(folder)          # its own tip and paper pictures become brush choices
    return Document.open(folder, item, KIND)


def snapshot(bridge):
    """The canvas as last drawn: the start screen's picture of this project."""
    return bridge.frames.provider.requestImage("", None, None)


FILES2D = AppFiles(
    app="2d", title="Rostrum2D", noun="project", ext=KIND.ext, untitled="Untitled", folder=settings.projects_dir,
    blank=blank, open=open_doc, resolve=resolve, sample="lull",
    guides=[(GUIDES / "first-animation.md", "Making your first animation"), (GUIDES / "the-screen.md", "The screen"),
            (GUIDES / "drawing.md", "Drawing")],
    after_copy=repoint, snapshot=snapshot)
