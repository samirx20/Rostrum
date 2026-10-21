"""The project's shared named markers ("logo lands", "drop"): one list for the whole project, read by every app
(project-service CONTRACT.md § 2, AGENTS.md rule 8). Cross-app timing ties to a marker by name, never a copied
number.

The list is a small document of its own, `docs/markers.mkr` in the project folder, so every change is an
operation in one history (undo, who changed what) like any other document:

    marker.add     name, at (seconds), optional id     → a new marker
    marker.move    at                                  → retime markers
    marker.rename  name                                → rename one marker (its id never changes)
    marker.remove                                      → delete markers

Times are seconds on the project timeline. Names are unique (case and spaces at the ends ignored).
Apps call `edit(folder, calls, who)` to change it and `listing(folder)` / `at(folder, name)` to read it.
"""
from __future__ import annotations

import re
from pathlib import Path

from .document import Document
from .errors import RostrumError, codes
from .kind import DocKind
from .params import Param
from .registry import Registry

ITEM = "markers"                    # docs/markers.mkr, .rostrum/markers.history.jsonl
REGISTRY = Registry()
_AT = dict(label="Time", unit="s", min=0, max=86400, step=0.01, group="Marker")
_REF = re.compile(r"^(?P<name>.+?)\s*(?P<off>[+-]\s*\d+(\.\d+)?)?$")


def _key(name: str) -> str:
    return " ".join(str(name).split()).lower()


@REGISTRY.operation("marker.add", "Add a named marker at a time (seconds on the project timeline).", params=[
    Param.text("name", label="Name", required=True, group="Marker"),
    Param.number("at", required=True, **_AT),
    Param.text("id", label="Id", help="Optional; made from the name when left out.")], label="Add marker")
def marker_add(ctx, targets, args):
    slug = re.sub(r"[^a-z0-9]+", "_", _key(args["name"])).strip("_") or "marker"
    id_ = args.get("id") or ctx.new_id(f"mk_{slug}")
    ctx.insert("root", "markers", {"id": id_, "type": "marker", "name": args["name"].strip(), "at": args["at"]})


@REGISTRY.operation("marker.move", "Move markers to a new time.", target="marker", label="Move marker",
                    params=[Param.number("at", required=True, **_AT)])
def marker_move(ctx, targets, args):
    for t in targets:
        ctx.set(t, "at", args["at"])


@REGISTRY.operation("marker.rename", "Rename a marker; what points at it by id keeps working.", target="marker",
                    label="Rename marker", params=[Param.text("name", label="Name", required=True, group="Marker")])
def marker_rename(ctx, targets, args):
    for t in targets:
        ctx.set(t, "name", args["name"].strip())


@REGISTRY.operation("marker.remove", "Delete markers.", target="marker", label="Delete marker",
                    importance="secondary")
def marker_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


def _check(data) -> list[str]:
    out, seen = [], {}
    for m in data.get("markers", []):
        k = _key(m.get("name", ""))
        if not k:
            out.append(f'marker {m["id"]} has no name')
        elif k in seen:
            out.append(f'two markers are called "{m["name"]}" ({seen[k]} and {m["id"]}); names must differ')
        seen.setdefault(k, m["id"])
        if not isinstance(m.get("at"), (int, float)) or m["at"] < 0:
            out.append(f'marker "{m.get("name")}" has a bad time {m.get("at")!r}; it must be 0 s or later')
    return out


KIND = DocKind("markers", ".mkr", REGISTRY, lists={"doc": ["markers"]}, check=_check,
               new=lambda: {"id": "root", "type": "doc", "markers": []})


def _exists(folder) -> bool:
    return (Path(folder) / "docs" / f"{ITEM}{KIND.ext}").is_file()


def open_markers(folder) -> Document:
    """The project's marker document (an empty one, not yet saved, when the project has no markers)."""
    if folder is None or not Path(folder).is_dir():
        raise RostrumError(codes.NOT_FOUND, "markers", str(folder), "is not a project folder")
    return Document.open(folder, ITEM, KIND) if _exists(folder) else Document.new(KIND, folder, ITEM)


def edit(folder, calls, who, label=None):
    """Apply marker operations as one change and save at once. Returns the Change (None: nothing changed)."""
    doc = open_markers(folder)
    change = doc.apply(calls, who, label=label)
    if change is not None:
        doc.save()
    return change


def _made_by(doc, id_):
    for c in doc.history.changes:
        if any(getattr(e, "item", {}).get("id") == id_ for e in c.edits):
            return str(c.who)
    return "outside"


def listing(folder, doc: Document | None = None) -> list[dict]:
    """Every marker, by time: {id, name, at, by, changed_by}. No marker document yet = []."""
    if doc is None and (folder is None or not _exists(folder)):
        return []
    doc = doc or open_markers(folder)
    out = []
    for m in doc.data["markers"]:
        last = doc.who_changed(m["id"])
        out.append({"id": m["id"], "name": m["name"], "at": m["at"], "by": _made_by(doc, m["id"]),
                    "changed_by": str(last.who) if last else "outside"})
    return sorted(out, key=lambda m: (m["at"], m["name"].lower()))


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


_TIMES: dict = {}       # path -> (file time, {name: seconds}); a frame-by-frame reader re-reads only on change


def times(folder) -> dict[str, float]:
    """{name: seconds} for every marker, by time; what expressions, flags and snapping read. Cheap to call often:
    the file is read again only when it changed. No project folder or no markers yet = {}."""
    if folder is None:
        return {}
    path = Path(folder) / "docs" / f"{ITEM}{KIND.ext}"
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return {}
    if _TIMES.get(path, (None,))[0] != stamp:
        data = open_markers(folder).data
        rows = sorted(data.get("markers", []), key=lambda m: m["at"])
        _TIMES[path] = (stamp, {m["name"]: float(m["at"]) for m in rows})
    return dict(_TIMES[path][1])


def lookup(times_: dict[str, float], name: str) -> float | None:
    """A name's seconds in a times() dict, case and outer spaces ignored; None when there is none."""
    want = _key(name)
    return next((t for n, t in times_.items() if _key(n) == want), None)
