"""A person's "file" is a project folder (rostrum_core/storage.py: docs/<item>.mtn + .rostrum/ history). This module is
everything about those folders that is not the screen: make one, find the document in one, the recovery copy, the
check that nobody else saved over the file, and the copy Save As makes. No Qt here.

Recovery copy: <project>/.rostrum/recovery/, the same storage.save format (its own docs/ and .rostrum/), so restoring
is Document.open on that folder. It never touches the saved document.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

from rostrum2d import KIND, settings
from rostrum_core import Document, RostrumError, Who, codes
from rostrum_core.storage import doc_hash, paths, save

ITEM = "main"                                     # the item a new project's document gets
BLANK = {"id": "main", "name": "Main", "width": 1920, "height": 1080, "fps": 25, "duration": 10.0}
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def clean_name(name: str) -> str:
    """A project name that is a valid folder name; a name with nothing left fails loudly."""
    out = _BAD.sub("", name).strip().rstrip(".")
    if not out:
        raise RostrumError(codes.BAD_ARGUMENT, "project", f'"{name}"', "is not a name a folder can have")
    return out


def untitled(root: Path | None = None) -> str:
    """"Untitled 1", "Untitled 2" …: the first not taken in the projects folder."""
    root, n = root or settings.projects_dir(), 1
    while (root / f"Untitled {n}").exists():
        n += 1
    return f"Untitled {n}"


def free_folder(name: str, root: Path | None = None) -> Path:
    folder = (root or settings.projects_dir()) / clean_name(name)
    if folder.exists():
        raise RostrumError(codes.CONFLICT, "project", str(folder), "already exists", hint="Pick another name.")
    return folder


def new_project(name: str, root: Path | None = None) -> Document:
    """A new project folder with one blank composition (1920 × 1080, 25 fps, 10 s), saved. The composition is the
    document's starting contents, not a change: a new project has nothing to undo."""
    doc = Document.new(KIND, folder=free_folder(name, root), item=ITEM, start=[{"op": "comp.add", "args": dict(BLANK)}])
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
                           hint=f"Pick the file in {p / 'docs'}.")
    raise RostrumError(codes.BAD_ARGUMENT, "open", str(p), f"is not a Rostrum2D project folder or {KIND.ext} file")


def disk_hash(folder, item) -> str | None:
    """The saved document's content hash (None when there is no file): what "nobody saved over it" compares."""
    f = paths(folder, item, KIND.ext)["doc"]
    if not f.is_file():
        return None
    return doc_hash(json.loads(f.read_text(encoding="utf-8"))["doc"])


# ---- the recovery copy ------------------------------------------------------------------------------------------
def recovery_folder(folder) -> Path:
    return Path(folder) / ".rostrum" / "recovery"


def save_into(doc, folder, item=None) -> Path:
    """The document, history and all, saved as `item` (its own by default) of another folder; `doc` is not changed."""
    item = item or doc.item_id or ITEM
    save(SimpleNamespace(folder=Path(folder), item_id=item, kind=doc.kind, base=doc.base, history=doc.history,
                         script_bases=doc.script_bases, data=doc.data))
    return paths(folder, item, KIND.ext)["doc"]


def write_recovery(doc) -> Path:
    """The unsaved document into the recovery folder (never over the saved file)."""
    return save_into(doc, recovery_folder(doc.folder))


def recovery_time(folder, item) -> float | None:
    """When the recovery copy was written, if it is newer than the saved document; else None."""
    rec = paths(recovery_folder(folder), item, KIND.ext)["doc"]
    saved = paths(folder, item, KIND.ext)["doc"]
    if not rec.is_file():
        return None
    t = rec.stat().st_mtime
    return t if not saved.is_file() or t > saved.stat().st_mtime else None


def open_recovery(folder, item) -> Document:
    """The recovery copy as the project's document (its folder the project's again): saving it writes the project."""
    doc = Document.open(recovery_folder(folder), item, KIND)
    doc.folder = Path(folder)
    return doc


def clear_recovery(folder) -> None:
    shutil.rmtree(recovery_folder(folder), ignore_errors=True)


# ---- Save As ----------------------------------------------------------------------------------------------------
def copy_project(src, dst: Path) -> None:
    """The whole project folder (other documents, markers, imported pictures, renders), never its recovery copy."""
    shutil.copytree(src, dst, ignore=lambda d, names: ["recovery"] if Path(d) == Path(src) / ".rostrum" else [])


def repoint_calls(doc, old, new) -> list[dict]:
    """Image and video layers whose file sits inside the old project folder (imports/) point into the new one."""
    old, calls = Path(old).resolve(), []
    for it in doc.items():
        src = it.get("src")
        if it.get("type") in ("image", "video") and src:
            try:
                rel = Path(src).resolve().relative_to(old)
            except ValueError:
                continue
            calls.append({"op": f"{it['type']}.set", "target": [it["id"]], "args": {"src": str(Path(new) / rel)}})
    return calls


def save_as(doc, name: str, who: Who, root: Path | None = None) -> Document:
    """A new project folder `name`: a copy of the project (if it has a folder) with this document saved in it, imported
    files pointed into the copy (one change). Returns the document opened from there; the old project is left as saved."""
    dst, item = free_folder(name, root), doc.item_id or ITEM
    if doc.folder and Path(doc.folder).is_dir():
        copy_project(doc.folder, dst)
    save_into(doc, dst, item)
    new = Document.open(dst, item, KIND)
    calls = repoint_calls(new, doc.folder, dst) if doc.folder else []
    if calls:
        new.apply(calls, who, label="Imported files now in the new project")
        new.save()
    return new
