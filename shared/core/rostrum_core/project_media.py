"""How a document's media files are stored and checked against the project folder (see project.py)."""
from __future__ import annotations

from pathlib import Path


def media_ref(folder, path) -> str:
    """How a document stores the file `path`: relative to the project folder (forward slashes) when it lies inside
    it, so the project can be copied or moved; else the path as given (a file the person keeps elsewhere)."""
    try:
        return Path(path).resolve().relative_to(Path(folder).resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def media_place(folder, value: str) -> str | None:
    """The place IN the project (relative) that a stored absolute path stands for, or None to leave it as it is: a file
    inside the folder, or one an older copy of the project still names from the folder it was copied FROM (the same
    place under `media/` here, and the old file is gone or the same size). A relative path or a file kept elsewhere: None."""
    p = Path(value)
    if not p.is_absolute():
        return None
    rel = media_ref(folder, p)
    if rel != str(p):
        return rel
    parts = p.parts
    if "media" not in parts:
        return None
    tail = Path(*parts[len(parts) - 1 - parts[::-1].index("media"):])
    here = Path(folder) / tail
    if here.is_file() and (not p.is_file() or p.stat().st_size == here.stat().st_size):
        return tail.as_posix()
    return None


def media_outside(folder, value: str) -> bool:
    """True for an absolute path to a file the project does not hold (it will not travel with the project)."""
    return bool(folder) and bool(value) and Path(value).is_absolute() and media_ref(folder, value) == value


def media_file(folder, value) -> Path:
    """The file a stored reference (`media_ref`) points to: an absolute path as it is, a relative one under the
    project folder (no folder: relative to the process, as a path always was)."""
    p = Path(value)
    return p if p.is_absolute() or folder is None else Path(folder) / p


def media_problems(folder, refs, outside: bool = True) -> list[dict]:
    """The file problems of a document, for any app: `refs` is [(item id, what it is called, stored path)], each with an
    optional fourth part naming which of the item's fields holds the file (".src"). A file that is not there is
    "missing-file" (names the item and the file); one the project does not hold is "outside-project" (it will not travel
    with the project; `outside=False` for files that are meant to stay where they are, like a LUT). Rows are
    {kind, item, message, fix}."""
    out = []
    for item, name, value, *field in refs:
        name = f'{name} ({item}){field[0] if field else ""}'
        if not media_file(folder, value).is_file():
            out.append({"kind": "missing-file", "item": item, "message": f'{name}: no file at "{value}"',
                        "fix": "Put the file back, or point it at the file again (absolute, or relative to the project folder)"})
        elif outside and media_outside(folder, value):
            out.append({"kind": "outside-project", "item": item, "message": f'{name}: its file is kept outside the project '
                        f'("{value}"), so it will not travel with it', "fix": "Record or import the file again to keep a copy in the project"})
    return out
