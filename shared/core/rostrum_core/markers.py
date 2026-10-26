"""The project's shared named markers ("logo lands", "drop"): one list for the whole project, read by every app
(project-service CONTRACT.md § 2, AGENTS.md rule 8). Cross-app timing ties to a marker by name, never a copied
number.

The list is a small document of its own, `docs/markers.mkr` in the project folder, so every change is an
operation in one history (undo, who changed what) like any other document:

    marker.add     name, at (seconds), optional id     → a new marker
    marker.move    at                                  → retime markers
    marker.rename  name                                → rename one marker (its id never changes)
    marker.remove                                      → delete markers
    marker.follow  item, part, use                     → keep a marker on another app's item (links.py)
    marker.unfollow                                    → let it stand on its own again
    marker.keep    at                                  → a following marker put back on its item (links.refresh)
    marker.set     name, at, colour                    → read as marker.move / rename / colour (what Sound's own markers
                                                         call it), with a note saying so

Times are seconds on the project timeline. Names are unique (case and spaces at the ends ignored).
Apps call `edit(folder, calls, who)` to change it and `listing(folder)` / `at(folder, name)` to read it.
"""
from __future__ import annotations

from .document import Document
from .errors import RostrumError, codes
from .marker_ops import ITEM, KIND, REGISTRY, _AT, _check, _REF  # noqa: F401  (one import for apps)
from .marker_cache import (_DOCS, _WATCHED, _exists, current, edit, open_markers, open_to_change,  # noqa: F401
                           refresh, watch)
from .marker_times import EXT, _key, lookup, refuse_clashes, times, used, version  # noqa: F401  (one import for apps)

_LISTED: dict = {}      # str(folder) -> (document, its data, listing rows)


def _made_by(doc, id_):
    for c in doc.history.changes:
        if any(getattr(e, "item", {}).get("id") == id_ for e in c.edits):
            return str(c.who)
    return "outside"


def listing(folder, doc: Document | None = None) -> list[dict]:
    """Every marker, by time: {id, name, at, by, changed_by}. No marker document yet = []."""
    cached = doc is None
    doc = doc or current(folder)
    if doc is None:
        return []
    got = _LISTED.get(str(folder)) if cached else None
    if got is not None and got[0] is doc and got[1] is doc.data:
        return [dict(r) for r in got[2]]
    out = []
    for m in doc.data["markers"]:
        last = doc.who_changed(m["id"])
        out.append({"id": m["id"], "name": m["name"], "at": m["at"], "owner": m.get("owner", ""),
                    "colour": m.get("colour", ""), "follows": m.get("follows"), "by": _made_by(doc, m["id"]),
                    "changed_by": str(last.who) if last else "outside"})
    out = sorted(out, key=lambda m: (m["at"], m["name"].lower()))
    if cached:
        _LISTED[str(folder)] = (doc, doc.data, out)
    return [dict(r) for r in out]


def find(markers: list[dict], name_or_id: str) -> dict:
    """One marker by name (case-insensitive) or id; a loud error naming the markers that exist."""
    for m in markers:
        if m["id"] == name_or_id or _key(m["name"]) == _key(name_or_id):
            return m
    raise RostrumError.not_found("markers", "marker", name_or_id, [m["name"] for m in markers],
                                 "the project's markers")


def at(folder, ref: str, markers: list[dict] | None = None) -> float:
    """Seconds of a marker reference: "logo lands", "drop+0.5", "drop - 0.25"."""
    m = _REF.match(ref.strip())
    if not m:
        raise RostrumError(codes.BAD_ARGUMENT, "markers", f'"{ref}"', "is not a marker reference",
                           ['"drop"', '"drop+0.5"'])
    markers = listing(folder) if markers is None else markers
    off = float(m.group("off").replace(" ", "")) if m.group("off") else 0.0
    try:
        return float(find(markers, m.group("name"))["at"]) + off
    except RostrumError:
        if off:
            raise
        return float(find(markers, ref.strip())["at"])      # a name that itself ends in "-2" or "+1"
