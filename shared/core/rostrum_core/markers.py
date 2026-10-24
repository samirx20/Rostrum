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

Times are seconds on the project timeline. Names are unique (case and spaces at the ends ignored).
Apps call `edit(folder, calls, who)` to change it and `listing(folder)` / `at(folder, name)` to read it.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import links
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
        f = ctx.item(t).get("follows")
        if f:
            ctx.fail(codes.BAD_ARGUMENT, f'marker "{ctx.item(t)["name"]}"', f'follows "{f["part"]}" in "{f["item"]}"; '
                     "it moves with it", hint="Move that instead, or marker.unfollow first.")
        ctx.set(t, "at", args["at"])


@REGISTRY.operation("marker.keep", "Put following markers back on their item's time (links.refresh does this).",
                    target="marker", label="Markers follow their items", importance="deep",
                    params=[Param.number("at", required=True, **_AT)])
def marker_keep(ctx, targets, args):
    for t in targets:
        if not ctx.item(t).get("follows"):
            ctx.fail(codes.BAD_ARGUMENT, f'marker "{ctx.item(t)["name"]}"', "follows nothing", hint="Use marker.move.")
        ctx.set(t, "at", args["at"])


@REGISTRY.operation("marker.follow", "Keep a marker on another app's item: a part's start or end (a live link, "
                    "links.py). It moves whenever that part moves, even with its app closed.", target="marker",
                    label="Follow", importance="deep", params=[
                        Param.text("item", label="Item", required=True, help="The project item (\"scene1\")"),
                        Param.text("part", label="Part", required=True, help="Its part (a 2D layer id)"),
                        Param.choice("use", links.USES, label="At its", default="start")])
def marker_follow(ctx, targets, args):
    for t in targets:
        ctx.set(t, "follows", {"item": args["item"], "part": args["part"], "use": args.get("use", "start")})


@REGISTRY.operation("marker.unfollow", "Let following markers stand on their own (they stay where they are).",
                    target="marker", label="Stop following", importance="deep")
def marker_unfollow(ctx, targets, args):
    for t in targets:
        if ctx.item(t).get("follows"):
            ctx.set(t, "follows", None)


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
        f = m.get("follows")
        if f is not None and not (isinstance(f, dict) and f.get("item") and f.get("part")
                                  and f.get("use", "start") in links.USES):
            out.append(f'marker "{m.get("name")}" follows {f!r}; it needs an item, a part and start / end')
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
    doc = Document.open(folder, ITEM, KIND) if _exists(folder) else Document.new(KIND, folder, ITEM)
    links.watch(doc)                        # following markers keep their items' times, in the same step
    return doc


def open_to_change(folder) -> Document:
    """The marker document, live (live.keep): a change locks the file, takes in what other programs saved, and saves."""
    from .live import keep
    doc = current(folder) or open_markers(folder)
    keep(doc)
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
    looked at on each call (one stat); watched, never: `refresh` does it on the screen's poll."""
    if folder is None:
        return None
    key = str(folder)
    got = _DOCS.get(key)
    if got is not None and (key in _WATCHED or got[0] == version(folder)):
        return got[1]
    if not _exists(folder):
        _DOCS.pop(key, None)
        return None
    doc = open_markers(folder)
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
    if got[1].live is not None:
        got[1].live.catch_up()
        _DOCS[key] = (stamp, got[1])
    else:
        del _DOCS[key]


def edit(folder, calls, who, label=None):
    """Apply marker operations as one change, saved at once through the one door. Returns the Change (None: nothing
    changed)."""
    return open_to_change(folder).apply(calls, who, label=label)


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
