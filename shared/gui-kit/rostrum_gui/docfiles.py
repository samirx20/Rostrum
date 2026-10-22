"""One automatic-save model for every app's projects (INTERACTION.md 1.19, kit piece 13). No Qt, no app knowledge.

Every project window holds its document live (`rostrum_core.live.keep` + the kit's `LiveLink`): each change is on
disk as it happens, through the same door an agent's server uses. So there is no Save, no unsaved mark, no
"Save changes?" and no recovery copy. What a person still needs, here once for every app:

    AppFiles(...)                 the app's thin adapter: its kind, folder, how to make a blank one, how to open one
    projects_root(kind)           where New puts projects (a scripted run's scratch folder, never the person's)
    new_folder(root, base)        "Untitled", "Untitled 2" …: the first name not taken
    recent(kind) / remember(...)  Open recent, newest first (in userhome: scripted runs never touch the person's)
    duplicate(folder, dest)       a separate copy of the whole project folder
    rename(folder, name)          the project folder renamed in place (clicking its name in the top bar)
    version_name()                a version's default name: the time ("22 Oct 14:32")
    open_whole(kind, folder, item) a damaged or newer file refused in plain words that say nothing was changed
    (project_files / file_repairs.py: "Open the last version that works", Find… for missing files, reopen at the same place)
    thumb(folder, item)           where a project's picture for the start screen lives
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from rostrum_core import RostrumError, codes, userhome
from rostrum_core import recent as recent_list

UNTOUCHED = "Nothing was changed."
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SKIP = shutil.ignore_patterns("*.lock", "*.partial", "sound-open.json", "recovery")   # never part of a copy


@dataclass
class AppFiles:
    app: str                                   # "2d", "sound": the recent list's name, the sample's app
    title: str                                 # "Rostrum2D": in refusals ("saved by a newer Rostrum2D")
    noun: str                                  # "project", "song"
    ext: str                                   # the document file's extension (".mtn")
    untitled: str                              # "Untitled", "Untitled song"
    folder: Callable[[], Path]                 # the app's own projects folder (a person's run)
    blank: Callable[[Path | None], object]     # a new blank Document saved in this folder (None: in memory only)
    open: Callable[[Path, str], object]        # the Document read whole, else a RostrumError
    resolve: Callable[[Path], tuple]           # a picked file or folder -> (project folder, item)
    sample: str = ""                           # rostrum_core.samples name ("lull"); "" = none
    guides: list = field(default_factory=list)  # [(Path to a .md, label)], the start screen shows up to three
    after_copy: Callable | None = None         # (copy's Document, old folder, new folder) -> calls to point its files home
    snapshot: Callable | None = None           # (bridge) -> a QImage of the work, for the start screen's picture
    doc_kind: object = None                    # the app's DocKind: lets "Open the last version that works" rebuild from history
    place: Callable | None = None              # (bridge) -> dict: where the person is (scene, selection, playhead, view…)
    restore_place: Callable | None = None      # (bridge, dict) -> None: put it back after the project is shown
    refs: Callable | None = None               # (doc) -> [(item id, field, path)]: every file the document uses (Find…)
    ref_op: Callable | None = None             # (doc, item id) -> the operation that sets that item's file field


def projects_root(kind: AppFiles) -> Path:
    """Where New puts projects. A scripted run (a layout check, a proof, a test) uses its scratch home's folder,
    unless ROSTRUM_PROJECTS_DIR says where."""
    if os.environ.get("ROSTRUM_PROJECTS_DIR"):
        root = Path(os.environ["ROSTRUM_PROJECTS_DIR"])
    elif userhome.scripted():
        root = userhome.home() / "projects"
    else:
        root = Path(kind.folder())
    root.mkdir(parents=True, exist_ok=True)
    return root


def clean(name: str) -> str:
    """A name a folder can have; a name with nothing left fails loudly."""
    out = _BAD.sub("", name).strip().rstrip(".")
    if not out:
        raise RostrumError(codes.BAD_ARGUMENT, "name", f'"{name}"', "is not a name a folder can have",
                           hint=f"Use letters, numbers and spaces. {UNTOUCHED}")
    return out


def new_folder(root: Path, base: str) -> Path:
    """`base`, then `base 2`, `base 3` …: the first folder not taken."""
    folder, n = Path(root) / base, 1
    while folder.exists():
        n += 1
        folder = Path(root) / f"{base} {n}"
    return folder


def name_of(folder, item: str, main: str = "") -> str:
    """The name a person sees: the project folder's name, with the item when it is not the folder's main one."""
    name = Path(folder).name
    return name if not main or item == main else f"{name} ({item})"


# ---- Open recent (the list itself: rostrum_core/recent.py, which the agent servers read too) -------------------------
def thumb(folder, item) -> Path:
    return Path(folder) / ".rostrum" / "thumbs" / f"{item}.png"


def when_text(t: float) -> str:
    """"Today, 14:32", "Yesterday, 09:05", "21 Oct, 18:40"."""
    d = datetime.fromtimestamp(t)
    days = (datetime.now().date() - d.date()).days
    day = "Today" if days == 0 else "Yesterday" if days == 1 else f"{d.day} {d:%b}"
    return f"{day}, {d:%H:%M}"


def recent(kind: AppFiles) -> list[dict]:
    """[{folder, item, name, when, thumb}] newest first; projects that are gone drop out."""
    out = []
    for r in recent_list.rows(kind.app, kind.ext):
        pic = thumb(r["folder"], r["item"])
        out.append({**r, "when": when_text(r["changed"]), "thumb": str(pic) if pic.is_file() else ""})
    return out


def remember(kind: AppFiles, folder, item, name: str) -> None:
    recent_list.remember(kind.app, kind.ext, folder, item, name)


# ---- Duplicate, versions, refusals ---------------------------------------------------------------------------------
def duplicate(folder, dest) -> Path:
    """Copy the whole project (documents, history, markers, imports, renders) to `dest`, a new or empty folder.
    The original is not touched. Refuses a folder that has anything in it, or one inside the project."""
    src, dest = Path(folder).resolve(), Path(dest).resolve()
    if dest == src or src in dest.parents:
        raise RostrumError(codes.BAD_ARGUMENT, "duplicate", str(dest), "is the project's own folder",
                           hint=f"Pick a folder outside it. {UNTOUCHED}")
    if dest.exists() and any(dest.iterdir()):
        raise RostrumError(codes.CONFLICT, "duplicate", str(dest), "already has files in it",
                           hint=f"Pick a new name, or an empty folder. {UNTOUCHED}")
    shutil.copytree(src, dest, dirs_exist_ok=True, ignore=SKIP)
    return dest


def rename(folder, name: str) -> Path:
    """The project folder renamed beside itself (its documents, history, pictures and renders go with it). A name
    taken, or a folder another program holds open, is refused in words and changes nothing; an agent that had the
    old folder open is refused loudly on its next step (its folder is gone), never writes a second copy."""
    src = Path(folder).resolve()
    dest = src.parent / clean(name)
    if dest == src:
        return src
    if dest.exists() and dest.resolve() != src:        # (a change of capitals only is the same folder on Windows)
        raise RostrumError(codes.CONFLICT, "rename", f'"{dest.name}"', "is already a project in this folder",
                           hint=f"Pick another name. {UNTOUCHED}")
    try:
        src.rename(dest)
    except OSError as e:
        raise RostrumError(codes.CONFLICT, "rename", f'"{src.name}"', "can't be renamed now: another program has "
                           "a file in it open", hint=f"Close it there, then try again. {UNTOUCHED} ({e})") from e
    return dest


def version_name(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"{now.day} {now:%b} {now:%H:%M}"


def open_whole(kind: AppFiles, folder, item):
    """The document read and checked whole, else a RostrumError whose words a person reads: what is wrong, what to
    do, and that nothing was changed (a damaged or newer file is never put on screen half-read)."""
    name = f'The {kind.noun} "{Path(folder).name}"'
    try:
        return kind.open(Path(folder), item)
    except RostrumError as e:
        if "newer" in e.problem:
            raise RostrumError(codes.CHECK_FAILED, "open", name, f"was saved by a newer {kind.title}",
                               hint=f"Update {kind.title} to open it. {UNTOUCHED}") from e
        hint = e.hint or ""
        raise RostrumError(e.code, "open", e.subject if e.subject.startswith("The ") else name,
                           e.problem if e.subject.startswith("The ") else f"didn't open: {e.subject} {e.problem}",
                           e.accepted, hint if "Nothing was changed" in hint else f"{hint} {UNTOUCHED}".strip()) from e
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, OSError) as e:
        raise RostrumError(codes.CHECK_FAILED, "open", name, "can't be opened: its file is damaged",
                           hint=f"{UNTOUCHED} Details: {type(e).__name__}: {e}.") from e


def said(e: Exception) -> str:
    """A refusal as the screen shows it: the sentence, then what to do (no "Error: open:" prefix)."""
    if isinstance(e, RostrumError):
        return " ".join(p for p in (f"{e.subject} {e.problem}.", e.hint) if p)
    return str(e)
