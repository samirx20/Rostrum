"""run_open_project's one path, shared by every app: check the folder and the name, make the folder when it is new
(with its folders above it), open, and say plainly what was made. Checks come first, so a refused call makes nothing.

Each app passes its own pieces: `docs_in(folder)` (its documents there, newest first), `default_item(folder, explicit)`
and `open_project(app, folder, items)`; `word` is what a person calls one document ("document", "song").
"""
from __future__ import annotations

from pathlib import Path

from .. import ids
from ..errors import RostrumError, codes
from .reply import Reply

TOOL = "run_open_project"


def folder_description(ext: str) -> str:
    return ("The project folder, an absolute path: one from run_open_project (what: recent), "
            f"any folder with docs/<item>.{ext}, or a new folder (made, with its folders above it, when it isn't there yet).")


def item_description(word: str, default: str) -> str:
    return (f"The {word} to open. Default: the one its recent row names, else the only / newest in the folder, "
            f'else a new "{default}". A name the folder doesn\'t have yet starts a new {word} of that name.')


def checked_folder(raw: str) -> Path:
    folder = Path(raw)
    if not folder.is_absolute():
        raise RostrumError(codes.BAD_ARGUMENT, TOOL, f'"{folder}"', "is not an absolute path",
                           ["C:/Users/<you>/Videos/<project>"], "Pass the whole path to the project folder.")
    if folder.exists() and not folder.is_dir():
        raise RostrumError(codes.BAD_ARGUMENT, TOOL, f'"{folder}"', "is a file, not a folder", [],
                           "Pass the project folder (the one holding docs/), or a new folder's path.")
    return folder


def open_folder(ctx, args, *, docs_in, default_item, open_project, word: str = "document") -> Reply:
    folder = checked_folder(args["folder"])
    found, made = docs_in(folder), not folder.exists()
    item = args.get("item") or default_item(folder, explicit=True)
    if not ids.is_valid(item):
        raise RostrumError(codes.BAD_ARGUMENT, TOOL, f'item "{item}"', f"is not a usable {word} name",
                           found, "Letters, digits, _ . - (not starting with a digit), e.g. \"teaser\".")
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RostrumError(codes.BAD_ARGUMENT, TOOL, f'"{folder}"', f"could not be made ({e.strerror})", [],
                           "Pass a folder you can write to.") from e
    new = ("" if item in found else f" Made the folder and started the {word}, empty." if made else
           f" Started the {word}, empty; the project's other {word}s: {', '.join(found)}." if found else f" Started the {word}, empty.")
    open_project(ctx.app, str(folder.resolve()), [item])
    return Reply(f'Opened {ctx.app.folder} ({word} "{item}").{new} Other tools now work on it.',
                 {"folder": ctx.app.folder, "item": item, "documents": sorted(ctx.app.documents), "others": found, "new": item not in found})
