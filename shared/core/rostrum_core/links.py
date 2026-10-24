"""Live links between apps (project-service CONTRACT.md § 3): the first kind, a shared marker that keeps itself on
another app's item. 2D's "Logo · sound" cue marker follows the logo layer's start, so Sound's cue under it moves when
the layer moves, and when a marker the layer is timed on moves in Sound with 2D closed.

The one source of truth is the marker: `follows: {"item": "scene1", "part": "logo", "use": "start"}`, set by the
`marker.follow` operation (markers.py) and cleared by `marker.unfollow`. `listing(folder)` shows every link in the
contract's shape. `refresh(folder, who)` puts each following marker on its item's time now, as one change.

How a time is found is the owning app's: a resolver registered for the item's kind,

    links.register("2d", time_of)        # time_of(folder, item_id, part, use, times, doc=None) -> seconds | None

or an installed package's entry point in group "rostrum.links" (name = the kind), so Sound can keep a 2D marker in
place without 2D open. `times` is {marker name: seconds} as the markers stand now; `doc` is the item's open document
when the caller has it. None = the part is gone: the marker stays and the link is reported broken, never silent.

Who keeps them in place:
- the markers document itself (`watch`, hooked up by markers.open_markers): every change made in this program moves
  the followers in the same step (joint.py), so Ctrl+Z takes both back;
- the owning app, after a change to its own document (2D: `refresh(folder, who, docs={doc.item_id: doc})`).
Nothing moves while a step is being undone or redone (joint.replaying): the step's own changes are the truth.
A link problem (no resolver, part gone, a loop) goes to `problems(folder)` and every `on_problem` listener.
"""
from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path

from . import joint
from .errors import RostrumError, codes

USES = ["start", "end"]
_RESOLVERS: dict[str, object] = {}
_PROBLEMS: dict[str, list[str]] = {}
_LISTENERS: list = []
PASSES = 4                                   # a follower timed on another follower settles in a few passes


def register(kind: str, time_of):
    _RESOLVERS[kind] = time_of


def resolver(kind: str):
    if kind not in _RESOLVERS:
        for ep in entry_points(group="rostrum.links"):
            if ep.name == kind:
                _RESOLVERS[kind] = ep.load()
    return _RESOLVERS.get(kind)


def on_problem(fn):
    """`fn(folder, [lines])` whenever a refresh finds broken links (the Problems chip, a server's log)."""
    _LISTENERS.append(fn)
    return lambda: _LISTENERS.remove(fn)


def problems(folder) -> list[str]:
    return list(_PROBLEMS.get(str(Path(folder)), []))


def listing(folder, doc=None) -> list[dict]:
    """Every live link: {link, from, use, into, marker} in CONTRACT § 3's shape ("scene1#logo" → "markers#mk_…")."""
    from .markers import current
    doc = doc or current(folder)
    if doc is None:
        return []
    return [{"link": f'lnk_{m["id"]}', "from": f'{m["follows"]["item"]}#{m["follows"]["part"]}',
             "use": m["follows"].get("use", "start"), "into": f'markers#{m["id"]}', "marker": m["name"]}
            for m in doc.data["markers"] if m.get("follows")]


def _kind_of(folder, item_id) -> str:
    from .project import item
    return item(folder, item_id)["kind"]


def _wanted(folder, mdoc, docs, only) -> tuple[list, list[str]]:
    """[(marker id, seconds now)] for followers off their item's time, and the problems found."""
    times = {m["name"]: float(m["at"]) for m in mdoc.data["markers"]}
    calls, bad = [], []
    for m in mdoc.data["markers"]:
        f = m.get("follows")
        if not f or (only and f["item"] not in only):
            continue
        try:
            kind = _kind_of(folder, f["item"])
        except RostrumError:
            bad.append(f'marker "{m["name"]}" follows "{f["item"]}", which is not in this project any more')
            continue
        fn = resolver(kind)
        if fn is None:
            bad.append(f'marker "{m["name"]}" follows a {kind} item, but no installed app can read its times '
                       f'(install the {kind} app)')
            continue
        try:
            t = fn(folder, f["item"], f["part"], f.get("use", "start"), times, (docs or {}).get(f["item"]))
        except Exception as e:  # noqa: BLE001  one broken link never stops the others; said in words
            bad.append(f'marker "{m["name"]}" could not follow "{f["part"]}" in "{f["item"]}": '
                       + (e.line() if hasattr(e, "line") else str(e)))
            continue
        if t is None:
            bad.append(f'marker "{m["name"]}" follows "{f["part"]}" in "{f["item"]}", which is gone; it stays at '
                       f'{float(m["at"]):g} s')
        elif abs(max(0.0, t) - float(m["at"])) > 1e-6:
            calls.append({"op": "marker.keep", "target": [m["id"]], "args": {"at": round(max(0.0, t), 6)}})
    return calls, bad


def refresh(folder, who, docs: dict | None = None, mdoc=None, only=None) -> list[str]:
    """Put every following marker (of items in `only`, default all) on its item's time, one change per pass in the
    open step. Returns the names moved. A loop (followers that never settle) is refused loudly."""
    if folder is None or joint.replaying():
        return []
    from .markers import current, open_to_change
    if mdoc is None and current(folder) is None:
        return []
    mdoc = mdoc or open_to_change(folder)
    moved, bad = [], []
    for _ in range(PASSES):
        calls, bad = _wanted(folder, mdoc, docs, only)
        if not calls:
            break
        names = {m["id"]: m["name"] for m in mdoc.data["markers"]}
        moved += [names[c["target"][0]] for c in calls]
        with _quiet(mdoc):
            mdoc.apply(calls, who, label="Markers follow their items")
    else:
        raise RostrumError(codes.CONFLICT, "links", "following markers", "keep moving each other (a loop)",
                           hint="Unfollow one of the markers that follow each other.")
    _say(folder, bad)
    return list(dict.fromkeys(moved))


def _say(folder, bad):
    key = str(Path(folder))
    if bad != _PROBLEMS.get(key, []):
        _PROBLEMS[key] = bad
        for fn in list(_LISTENERS):
            fn(folder, list(bad))


class _quiet:
    """The markers document's own watcher stays out of refresh's own changes."""
    def __init__(self, doc):
        self.doc = doc

    def __enter__(self):
        self.doc._links_busy = True

    def __exit__(self, *exc):
        self.doc._links_busy = False


def watch(mdoc):
    """Keep `mdoc`'s followers in place after every change made in this program (joint step: one undo). Changes
    taken in from another program (live catch-up) are that program's to follow."""
    def on(ev):
        c = ev.change
        if (ev.kind != "change" or c is None or getattr(mdoc, "_links_busy", False) or joint.current() != c.step
                or not c.original):
            return
        try:
            refresh(mdoc.folder, c.who, mdoc=mdoc)
        except Exception as e:  # noqa: BLE001  the marker change stands and is saved; the link problem is said
            _say(mdoc.folder, [e.line() if hasattr(e, "line") else f"Error: live links: {e}"])
    mdoc._links_busy = False
    return mdoc.subscribe(on)
