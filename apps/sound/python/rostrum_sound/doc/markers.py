"""Markers: the one place Sound READS them (their list, a marker's time, `"#drop+0.5"` made seconds).

    markers.items(doc)             # [(name, item)]: the document's own markers, then the project's (shared) ones
    markers.all(doc)               # [(name, seconds)] by time (own=True: only the document's own)
    markers.time_of(doc, "drop")   # seconds; raises a not-found error naming the marker (and the ones that exist)
    markers.resolve(doc, "#drop+0.5", where)   # seconds; any other time is returned as written
    markers.ref("#logo lands+0.5") # "logo lands" (the marker a time names) or None
    markers.used(doc)              # {name: seconds} of the markers the document names: part of a render's key

`doc` is a document's root dict. Two kinds of marker:
- **project markers** (shared/project-service/MARKERS.md): one list for the whole project, in seconds, owned by
  the project service. Read here through `rostrum_core.markers`; changed with `markers.edit(folder, …)` (the
  `edit_markers` tool), never by a Sound operation. Their item is `{"id", "name", "at", "shared": True}`.
- **the document's own** (`doc["markers"]`, `marker.add / set / remove` in doc/ops_mix.py): may sit on a beat.

A name used by both is a loud error (manager, S11). Names match case-insensitively, as the project's do.
Which project: the folder this process works in (`use_project`, set when the MCP app or the screen opens a
project; `with project(folder):` for one block). No project = only the document's own markers.
A project marker renamed elsewhere: `renames(doc)` finds the old names the document still uses; the Sound
operation `marker.follow` rewrites them (doc/ops_mix.py), all in one change.
"""
from __future__ import annotations

from contextlib import contextmanager

from rostrum_core import markers as shared
from rostrum_core.edits import Set
from rostrum_core.errors import RostrumError, codes
from rostrum_core.marker_times import REF, _key as key, ref, split  # the one reader of "#drop+0.5" (every app)

from . import tempo

_PROJECT: list = [None]          # the project folder this process works in
_ROWS: dict = {}                 # folder -> (version, listing): re-read only when the markers file changed


def use_project(folder):
    """The project whose shared markers every reader below sees (None: only the document's own)."""
    _PROJECT[0] = folder


@contextmanager
def project(folder):
    old, _PROJECT[0] = _PROJECT[0], folder
    try:
        yield
    finally:
        _PROJECT[0] = old


def project_rows() -> list[dict]:
    """The project's markers: [{id, name, at, owner, colour, by, changed_by}] by time ([] without a project)."""
    folder = _PROJECT[0]
    if folder is None:
        return []
    v = shared.version(folder)
    if _ROWS.get(folder, (None,))[0] != v:
        _ROWS[folder] = (v, shared.listing(folder))
    return _ROWS[folder][1]


def items(doc: dict) -> list[tuple[str, dict]]:
    """[(name, marker item)]: the document's own, then the project's. The one place that decides which exist."""
    own = [(m.get("name", m["id"]), m) for m in doc.get("markers", [])]
    rows = project_rows()
    shared.refuse_clashes({r["name"]: r["at"] for r in rows}, [n for n, _ in own], "sound markers")
    return own + [(r["name"], {"id": r["id"], "name": r["name"], "at": r["at"], "shared": True}) for r in rows]


def by_name(doc: dict) -> dict:
    """{name key: (name, item)}: names compared case- and outer-space-insensitively."""
    return {key(n): (n, m) for n, m in items(doc)}


def has(doc: dict, name: str) -> bool:
    return key(name) in by_name(doc)


def _at(marker: dict, name: str, doc: dict, seen) -> float:
    at = resolve(doc, marker.get("at", 0), f"marker {name}", seen)
    return tempo.seconds_at(doc, float(at["beat"])) if isinstance(at, dict) else float(at)


def all(doc: dict, own: bool = False) -> list[tuple[str, float]]:  # noqa: A001  reads as `markers.all(doc)`
    """[(name, seconds)] by time; own=True: only the document's own markers."""
    marks = [(n, m) for n, m in items(doc) if not (own and m.get("shared"))]
    return sorted(((n, _at(m, n, doc, ())) for n, m in marks), key=lambda p: p[1])


def time_of(doc: dict, name: str, where: str = "marker", seen=()) -> float:
    """The marker's time in seconds. A missing marker is a loud error that names it."""
    marks = by_name(doc)
    if key(name) not in marks:
        raise RostrumError.not_found(where, "marker", name, [n for n, _ in marks.values()],
                                     "the document's and the project's markers")
    if key(name) in seen:
        raise RostrumError(codes.CHECK_FAILED, where, f'marker "{name}"', "refers to itself through other markers")
    n, m = marks[key(name)]
    return _at(m, n, doc, (*seen, key(name)))


def resolve(doc: dict, value, where: str, seen=()):
    """The time with a marker reference made seconds; seconds and beats are kept as written."""
    parts = split(value)
    if parts is None:
        return value
    name, offset = parts
    at = time_of(doc, name, where, seen)
    if at + offset < 0:
        raise RostrumError(codes.BAD_ARGUMENT, where, value, "lands before the start of the mix")
    return round(at + offset, 6)


def refs_in(node):
    """Every marker reference string anywhere inside a value (a whole document, an item, a field). A colour
    ("#4aa3ff") is not one."""
    if isinstance(node, str):
        if ref(node):
            yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            if k != "colour":
                yield from refs_in(v)
    elif isinstance(node, list):
        for v in node:
            yield from refs_in(v)


def used(doc: dict) -> dict[str, float]:
    """{name: seconds} of every marker the document names: moving one it doesn't name changes nothing here."""
    return {n: time_of(doc, n) for n in sorted({ref(r) for r in refs_in(doc)}, key=key)}


def renames(doc: dict) -> dict[str, str]:
    """{old name: current name} for names the document uses that a project marker was renamed away from (read
    from the marker list's own history: a marker's id never changes). Empty when nothing needs following."""
    rows = project_rows()
    lost = {key(ref(r)): ref(r) for r in refs_in(doc)} if rows else {}
    lost = {k: n for k, n in lost.items() if k not in by_name(doc)}
    if not lost:
        return {}
    former = {}
    for change in shared.open_markers(_PROJECT[0]).history.changes:
        for e in change.edits:
            if isinstance(e, Set) and e.path == ["name"] and isinstance(e.before, str):
                former[key(e.before)] = e.id
    now = {r["id"]: r["name"] for r in rows}
    return {n: now[former[k]] for k, n in lost.items() if former.get(k) in now}


def renamed(value, old: str, new: str):
    """`value` with every reference to marker `old` pointing at `new` (offsets kept); anything else as it was."""
    if isinstance(value, str):
        m = REF.match(value)
        return f"#{new}{value[m.end(1):]}" if m and key(m.group(1)) == key(old) else value
    if isinstance(value, list):
        return [renamed(v, old, new) for v in value]
    if isinstance(value, dict):
        return {k: renamed(v, old, new) for k, v in value.items()}
    return value
