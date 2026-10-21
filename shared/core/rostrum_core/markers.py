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
from .marker_times import EXT, _key, lookup, refuse_clashes, times, used, version  # noqa: F401  (one import for apps)

ITEM = "markers"                    # docs/markers.mkr, .rostrum/markers.history.jsonl (marker_times.py reads it)
REGISTRY = Registry()
_AT = dict(label="Time", unit="s", min=0, max=86400, step=0.01, group="Marker")
_REF = re.compile(r"^(?P<name>.+?)\s*(?P<off>[+-]\s*\d+(\.\d+)?)?$")


@REGISTRY.operation("marker.add", "Add a named marker at a time (seconds on the project timeline).", params=[
    Param.text("name", label="Name", required=True, group="Marker"),
    Param.number("at", required=True, **_AT),
    Param.text("id", label="Id", help="Optional; made from the name when left out."),
    Param.choice("owner", ["2d", "sound", "3d", "edit"], label="Made in", help="The app it belongs to (optional)."),
    Param.color("colour", label="Colour", group="Marker", importance="secondary")], label="Add marker")
def marker_add(ctx, targets, args):
    slug = re.sub(r"[^a-z0-9]+", "_", _key(args["name"])).strip("_") or "marker"
    id_ = args.get("id") or ctx.new_id(f"mk_{slug}")
    extra = {k: args[k] for k in ("owner", "colour") if args.get(k)}
    ctx.insert("root", "markers", {"id": id_, "type": "marker", "name": args["name"].strip(), "at": args["at"],
                                   **extra})


@REGISTRY.operation("marker.colour", "Change markers' colour.", target="marker", label="Marker colour",
                    importance="secondary", params=[Param.color("colour", label="Colour", required=True)])
def marker_colour(ctx, targets, args):
    for t in targets:
        ctx.set(t, "colour", args["colour"])


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


KIND = DocKind(ITEM, EXT, REGISTRY, lists={"doc": ["markers"]}, check=_check,
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
        out.append({"id": m["id"], "name": m["name"], "at": m["at"], "owner": m.get("owner", ""),
                    "colour": m.get("colour", ""), "by": _made_by(doc, m["id"]),
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
