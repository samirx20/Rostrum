"""The project's picture, for sound made to picture (no Qt widgets): kept in the document's `picture` field (so an
agent can set it and it survives save / load). Either a video file the user chose, or a link to a 2D item of the
project, "item:<id>", which shows that item's newest finished picture render (rostrum_core.project.latest_render).
A link follows new renders by itself; an item not rendered yet shows a clear "not rendered yet", never an old frame.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from rostrum_core import RostrumError, codes, project
from rostrum_sound.doc import times

LINK = "item:"
VIDEO = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


def items(folder) -> list[dict]:
    """The project's 2D items to pick from: [{id, label}] (label says when one has no render yet)."""
    if not folder or not Path(folder).is_dir():
        return []
    return [{"id": it["id"], "label": it["name"] + ("" if _video(it["renders"]) else " (not rendered yet)")}
            for it in project.items(folder, "2d")]


def items_note(folder) -> str:
    """Why the project's items can't be listed, in plain words ("" when there are some)."""
    if not folder or not Path(folder).is_dir():
        return "This song is not in a project folder, so there are no 2D items to pick from."
    return "" if items(folder) else "The project has no 2D items yet."


def _video(renders: list[dict]) -> str:
    """The newest picture render's video file, or ""."""
    r = next((r for r in renders if r["kind"] == "pictures"), None)
    f = next((f for f in r["files"] if f.lower().endswith(VIDEO)), None) if r else None
    return str(Path(r["path"]) / f) if f else ""


def resolve(value: str, folder) -> tuple[str, str]:
    """(the video file to show, why there is none). A file is itself; a link is its item's newest render."""
    if not value.startswith(LINK):
        return value, ""
    item_id = value[len(LINK):]
    if not folder:
        return "", f"This song is not in a project folder, so {item_id} can't be found."
    found = [it for it in project.items(folder) if it["id"] == item_id]
    if not found:
        return "", f"The project has no item {item_id}."
    r = project.latest_render(folder, item_id, "pictures")
    if r is None:
        return "", f"{found[0]['name']} is not rendered yet."
    video = _video([r])
    return (video, "") if video else ("", f"{found[0]['name']} v{r['version']:03d} has frames only, no video to show.")


class Follow(QObject):
    """Says when a linked item's newest render changes (a new one finished): the corner then loads it. Looks every
    2 s, and only while the picture is a link (a chosen file never changes by itself)."""
    changed = Signal()

    def __init__(self, get, parent=None):
        super().__init__(parent)
        self._get, self._last = get, None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(2000)

    def _tick(self):
        value, folder = self._get()
        if not value.startswith(LINK):
            self._last = None
            return
        now = resolve(value, folder)
        if self._last is not None and now != self._last:
            self.changed.emit()
        self._last = now


def start(root: dict) -> tuple[float, str]:
    """(when the picture's first frame is, in seconds; why it can't be worked out). The doc's `pictureAt` in any time
    form: a marker ("#logo") moves the picture when the marker moves."""
    at = root.get("pictureAt")
    if at is None:
        return 0.0, ""
    try:
        return times.seconds(at, root, "pictureAt"), ""
    except RostrumError as e:
        return 0.0, f"The picture's start can't be found: {e}"


def start_call(ref: str) -> dict:
    """Start the picture at a shared marker ("logo"), or at the start of the song ("")."""
    return {"op": "doc.set", "target": ["root"], "args": {"pictureAt": f"#{ref}" if ref else 0}}


def start_marker(root: dict) -> str:
    """The marker the picture starts on ("" when it starts at a plain time)."""
    return times.marker_ref(root.get("pictureAt")) or ""


def link_call(item_id: str) -> dict:
    return set_call(LINK + item_id)


def local(chosen: str) -> str:
    """A file the user picked (a path or a file:// URL) as a path; "" clears the picture. A file that isn't
    there is an error that says so."""
    if not chosen:
        return ""
    path = QUrl(chosen).toLocalFile() if chosen.startswith("file:") else chosen
    if not Path(path).is_file():
        raise RostrumError(codes.BAD_ARGUMENT, "picture", f'"{path}"', "is not a file on this machine", [])
    return str(Path(path))


def name(value: str, folder=None) -> str:
    if value.startswith(LINK):
        found = [it for it in items(folder) if it["id"] == value[len(LINK):]]
        return found[0]["label"] if found else value[len(LINK):]
    return Path(value).name


def url(path: str) -> str:
    return QUrl.fromLocalFile(path).toString() if path else ""


def set_call(path: str) -> dict:
    return {"op": "doc.set", "target": ["root"], "args": {"picture": path}}
