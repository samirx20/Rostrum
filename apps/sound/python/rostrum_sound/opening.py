"""Opening a song whole or not at all (docs/RELEASE.md line 13).

A song file that is damaged (cut short, edited by hand into the wrong shape, a history line broken), belongs to
another app, or was saved by a newer RostrumSound is refused with one plain sentence that names the song; it is
never put on screen half-read, and nothing is written over it. Every way a person opens a song comes through here
(Open, Open recent, a double-clicked .trk, the last song on start, crash recovery, the agent server).
"""
from __future__ import annotations

import json
from pathlib import Path

from rostrum_core import Document, RostrumError, codes
from .doc import KIND
from .doc import fields_design as FDS
from .doc import markers

APPS = {"rostrum-2d": "Rostrum2D", "rostrum-3d": "Rostrum3D", "rostrum-editor": "Rostrum Editor"}
UNTOUCHED = "Nothing was changed in it."


def open_whole(folder, item) -> Document:
    """The song, read and checked in full (every value, then the song's own check: rostrum_core's open); else a
    RostrumError in words a person reads."""
    name = f'The song "{Path(folder).name}"'
    try:
        with markers.project(folder):       # its check sees the project's shared markers ("#hush-2.2"), not only its own
            doc = Document.open(folder, item, KIND)
        doc.notes += FDS.retired(doc.data)  # a whoosh from before PURPOSE.md: opens, said plainly, refused at render
        return doc
    except RostrumError as e:
        raise _refused(name, e) from e
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as e:   # readable, but the wrong shape
        raise _damaged(name, f"its contents are not a song's ({type(e).__name__}: {e})") from e


def said(e: Exception) -> str:
    """What the screen shows for a refused open or save: the sentence itself, without the "Error: open:" prefix
    agents read (the screen already shows it in red, beside the File button)."""
    if isinstance(e, RostrumError):
        return " ".join(p for p in (f"{e.subject} {e.problem}.", e.hint) if p)
    return str(e)


def _damaged(name, detail) -> RostrumError:
    return RostrumError(codes.CHECK_FAILED, "open", name, "can't be opened: its file is damaged",
                        hint=f"{UNTOUCHED} Details: {detail}.")


def _refused(name, e: RostrumError) -> RostrumError:
    problem = e.problem
    if "newer version" in problem:
        return RostrumError(codes.CHECK_FAILED, "open", name, "was saved by a newer RostrumSound",
                            hint=f"Update RostrumSound to open it. {UNTOUCHED}")
    if problem.startswith("is a "):
        fmt = problem[5:].split()[0].strip("'\"")
        what = APPS.get(fmt, "different kind of")
        return RostrumError(codes.BAD_ARGUMENT, "open", name, f"is a {what} file, not a RostrumSound song",
                            hint="Open it in that app.")
    if isinstance(e.__cause__, json.JSONDecodeError) or "damaged" in problem or "add up" in problem:
        return _damaged(name, f"{e.subject} {problem}")
    return RostrumError(e.code, "open", name, problem, e.accepted, e.hint)
