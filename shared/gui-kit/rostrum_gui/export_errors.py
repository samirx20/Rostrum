"""A failed export in a person's words, in the one place an export error becomes a message (ExportSheet._go).
The full developer line goes to the console (agents and logs read it there); the top bar and the sheet get this.
An error from the core says it in its own words (RostrumError.person()); the common OS errors (a file or folder in the
way, a folder that is missing, no permission, a full disk) name what could not be saved and where; anything else keeps
its type and text, so nothing is hidden."""
from __future__ import annotations

import errno
import sys
from pathlib import Path


def _where(e: OSError) -> str:
    path = Path(str(e.filename)) if getattr(e, "filename", None) else None
    return f"{path.name} in {path.parent}" if path and path.parent.name else (str(path) if path else "that place")


def os_words(e: OSError, what: str) -> str:
    """`what`: what was being saved ("the video")."""
    here = _where(e)
    if isinstance(e, FileExistsError):
        return f"Couldn't save {what}: something named {here} is already there, where a folder is needed. Move or rename it, or pick another folder."
    if isinstance(e, PermissionError):
        return f"Couldn't save {what}: this computer won't let Rostrum write to {here}. Pick another folder."
    if isinstance(e, FileNotFoundError):
        return f"Couldn't save {what}: the folder {Path(str(e.filename)).parent if e.filename else 'for it'} is missing. Pick another folder."
    if e.errno == errno.ENOSPC:
        return f"Couldn't save {what}: the disk is full. Free some space, or pick another disk."
    return f"Couldn't save {what}: {e.strerror or e}."


def said(e: BaseException, what: str = "the file", fallback: str = "Error: export") -> str:
    """The person's message for `e` (the console gets the full line on stderr)."""
    cause = e if isinstance(e, OSError) else e.__cause__ if isinstance(e.__cause__, OSError) else None
    line = e.line() if hasattr(e, "line") else f"{fallback}: {type(e).__name__}: {e}"
    print(line, file=sys.stderr)
    if cause is not None:
        return os_words(cause, what)
    if hasattr(e, "person"):
        return e.person()
    return f"{fallback}: {type(e).__name__}: {e}"
