"""The project's picture, for sound made to picture (no Qt widgets): one video file, kept in the document's
`picture` field (so an agent can set it and it survives save / load). The project service has no list of items
to offer yet (shared/project-service is a contract so far), so the picture is a chosen file.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from rostrum_core import RostrumError, codes


def local(chosen: str) -> str:
    """A file the user picked (a path or a file:// URL) as a path; "" clears the picture. A file that isn't
    there is an error that says so."""
    if not chosen:
        return ""
    path = QUrl(chosen).toLocalFile() if chosen.startswith("file:") else chosen
    if not Path(path).is_file():
        raise RostrumError(codes.BAD_ARGUMENT, "picture", f'"{path}"', "is not a file on this machine", [])
    return str(Path(path))


def name(path: str) -> str:
    return Path(path).name


def url(path: str) -> str:
    return QUrl.fromLocalFile(path).toString() if path else ""


def set_call(path: str) -> dict:
    return {"op": "doc.set", "target": ["root"], "args": {"picture": path}}
