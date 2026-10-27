"""The marker document as one copy per project, so reading it costs no file work (see markers.py)."""
from __future__ import annotations

from pathlib import Path

from . import filestamps, links
from .document import Document
from .errors import RostrumError, codes
from .marker_ops import ITEM, KIND
from .marker_times import version


def _exists(folder) -> bool:
    """The project has a marker file (kept between a screen's ticks, filestamps.py; this process's own save forgets it,
    so the first marker shows at once; a project without markers asked the disk on every change)."""
    return filestamps.stamp(Path(folder) / "docs" / f"{ITEM}{KIND.ext}") is not None


def open_markers(folder) -> Document:
    """The project's marker document (an empty one, not yet saved, when the project has no markers)."""
    if folder is None or not Path(folder).is_dir():
        raise RostrumError(codes.NOT_FOUND, "markers", str(folder), "is not a project folder")
    doc = Document.open(folder, ITEM, KIND) if _exists(folder) else Document.new(KIND, folder, ITEM)
    links.watch(doc)                        # following markers keep their items' times, in the same step
    return doc


def open_to_change(folder) -> Document:
    """The marker document, live (live.keep): a change locks the file, takes in what other programs saved, and saves."""
    from .live import keep
    doc = current(folder)
    if doc is not None:
        keep(doc)
        return doc
    keep(doc := open_markers(folder))       # the first marker (saved now): this copy is the project's from now on
    _DOCS[str(folder)] = (version(folder), doc)
    return doc


# ---- one copy of the marker document per project, so reading it costs no file work ---------------------------------
_DOCS: dict = {}        # str(folder) -> (the file stamp it was read at, the document)
_WATCHED: dict = {}     # str(folder) -> screens that poll it: while watched, `current` looks at no file
_LISTED: dict = {}      # str(folder) -> (document, its data, listing rows)


def watch(folder):
    """A screen (the kit's MarkerWatch) takes over the looking: `current` answers from its copy and the screen calls
    `refresh(folder)` on its own poll and after its own edits. Returns the undo."""
    key = str(folder)
    _WATCHED[key] = _WATCHED.get(key, 0) + 1

    def stop():
        _WATCHED[key] = _WATCHED.get(key, 1) - 1
        if _WATCHED[key] <= 0:
            _WATCHED.pop(key, None)
    return stop


def current(folder) -> Document | None:
    """The project's marker document as this process holds it (None: no markers yet). Unwatched, the file's stamp is
    looked at on each call (one stat); watched, never, "no markers yet" included: `refresh` does it on the screen's
    poll (a screen asked it up to 12 times per change, each a look at a file that isn't there)."""
    if folder is None:
        return None
    key = str(folder)
    got = _DOCS.get(key)
    if got is not None and (key in _WATCHED or got[0] == version(folder)):
        return got[1]
    doc = open_markers(folder) if _exists(folder) else None
    _DOCS[key] = (version(folder), doc)
    return doc


def refresh(folder) -> None:
    """The marker file may have changed (a screen's poll, its own edit): catch the copy up (a live one takes in the
    new lines), or drop it so the next `current` reads again."""
    key = str(folder)
    got = _DOCS.get(key)
    stamp = version(folder)
    if got is None or got[0] == stamp:
        return
    if got[1] is not None and got[1].live is not None:
        got[1].live.catch_up()
        _DOCS[key] = (stamp, got[1])
    else:
        del _DOCS[key]


def edit(folder, calls, who, label=None):
    """Apply marker operations as one change, saved at once through the one door. Returns the Change (None: nothing
    changed)."""
    doc = open_to_change(folder)
    _refuse_song_clashes(folder, doc, calls)
    return doc.apply(calls, who, label=label)


def _refuse_song_clashes(folder, doc, calls):
    """One marker namespace: a project marker added, moved or renamed onto a song's own marker's name at another time
    is refused now, plainly (song_markers.refuse), not found later by an export that has drawn every frame."""
    from . import song_markers
    songs = song_markers.times(folder) if any(str(c.get("op", "")).startswith("marker.") for c in calls) else {}
    if not songs:
        return
    rows = {m["id"]: m for m in doc.data.get("markers", [])}
    for c in calls:
        op, a = c.get("op"), c.get("args") or {}
        made = [(a.get("name", ""), a.get("at"))] if op == "marker.add" else [
            (a.get("name", rows[t]["name"]), a.get("at", rows[t]["at"])) for t in c.get("target") or [] if t in rows
            if op in ("marker.move", "marker.rename", "marker.set", "marker.keep")]
        for name, at in made:
            if name and isinstance(at, (int, float)):
                song_markers.refuse(name, float(at), songs, op)
