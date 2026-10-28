"""Time by name in a 2D script: every time may be seconds or a shared marker (`"#reveal+0.5"`), read through the one
reader every app shares (rostrum_core.marker_times), so a script never copies a marker's number (AGENTS.md rule 8).

    reveal = marker("reveal", 3)                      # a shared project marker, the same one edit_markers makes
    title = text("title", start=reveal + 0.5)         # "#reveal+0.5": arithmetic on a marker time stays on the marker
    title.key("opacity", {reveal + 0.5: 0, reveal + 0.9: 1})
    sub.key("opacity", {after(title, 0.2): 0, after(title, 0.6): 1})   # when title's last key lands, + 0.2 s
    for t, card in stagger(cards, every=0.5, start="#in"):              # t = "#in", "#in+0.5", "#in+1" …
        card.key("y", {t: 900, t + 0.4: 700})

`marker(name, at)` publishes the marker when the script has run (one step in the markers' history, by the script); a
re-run moves it, a removed line removes it. Only the markers this script made are ever touched (their ids carry the
document and the script's name): a person's marker or another app's of the same name at another time is a loud error.

A layer's `start="#m+0.5"` is stored as Timed from marker "m" with Starts at 0.5, so dragging the marker later moves
the layer with its keys. The numbers written in the script stay composition seconds all the same: at the end of the
run the layer's plain key times (and its children's) are written counted from the marker (`_count_from`), so a key
written at 3.6 s lands at 3.6 s. `end="#out"` is Ends at marker; `end="#out+0.5"` (an offset Ends at marker can't
hold) is that moment in seconds. Other calls' times (tap, scramble, sample, beats) become seconds when the script runs.
"""
from __future__ import annotations

import re

from rostrum_core import markers as M
from rostrum_core.marker_times import _key, lookup, seconds as _seconds, split, write
from rostrum_core.who import Who

from . import fields as F

END_OF_COMP = 36000.0
KEYED = ("effects", "masks", "layers", "bones", "iks", "binds", "stops")     # retime.CHILDREN: lists with keys of their own


class Time(str):
    """A time on a marker that adds like a number: `Time("#in") + 0.5` is "#in+0.5"; it is the string a key takes."""

    def __new__(cls, ref: str):
        parts = split(ref)
        if parts is None:
            raise ValueError(f'{ref!r} is not a marker time; they read "#drop", "#drop+0.2", "#hush-0.5"')
        out = str.__new__(cls, write(*parts))
        out.marker, out.offset = parts
        return out

    def __add__(self, by):
        if isinstance(by, bool) or not isinstance(by, (int, float)):
            raise TypeError(f'{self} + {by!r}: add seconds to a marker time ("#in" + 0.5)')
        return Time(write(self.marker, round(self.offset + by, 6)))

    __radd__ = __add__

    def __sub__(self, by):
        if isinstance(by, Time) and _key(by.marker) == _key(self.marker):
            return round(self.offset - by.offset, 6)
        return self + (-by if isinstance(by, (int, float)) and not isinstance(by, bool) else by)


def _state(build):
    if not hasattr(build, "time_marks"):
        build.time_marks, build.time_from = {}, {}      # {name: seconds} this script publishes; {layer id: (node, s)}
    return build


def _folder(build):
    doc = getattr(build, "doc", None)
    if doc is not None and getattr(doc, "folder", None) is not None:
        return doc.folder
    from .lipsync.script import _folder as host
    from .ops_timing import _PROJECT
    return host() or _PROJECT[0]


def times(build) -> dict[str, float]:
    """{name: seconds}: the project's shared markers (and songs'), with the markers this script makes over them."""
    shared = M.times(_folder(build)) if _folder(build) is not None else {}
    mine = _state(build).time_marks
    return {**{n: t for n, t in shared.items() if lookup(mine, n) is None}, **mine}


def seconds(build, value, where: str) -> float:
    """A script time as seconds: a number as is, a marker time from times(); a missing marker fails naming them all."""
    return _seconds(value, times(build), where)


def fill(build, node: dict, values: dict) -> dict:
    """Build.fill's time words: a layer's start / end given as a marker time (see the module's doc)."""
    if F.param(node["type"], "start") is None or not ({"start", "end"} & set(values)):
        return values
    out, st = dict(values), _state(build)
    s = out.get("start")
    if isinstance(s, str):
        name, off = split(s) or (None, 0.0)
        at = seconds(build, s, f'{node["id"]}.start')          # fails loudly on a bad or missing marker
        out.update(marker=name, start=off)
        st.time_from[node["id"]] = (node, at - off)
    elif s is not None and node["id"] in st.time_from:          # back to plain seconds: no longer from the marker
        del st.time_from[node["id"]]
        out.setdefault("marker", "")
    e = out.get("end")
    if isinstance(e, str):
        name, off = split(e) or (None, 0.0)
        at = seconds(build, e, f'{node["id"]}.end')
        if abs(off) < 1e-6:
            out.pop("end")
            out["endMarker"] = name
        else:
            node["endMarker"] = ""
            own = (out.get("marker") or node.get("marker")) if node["id"] not in st.time_from else None
            out["end"] = at - (lookup(times(build), own) or 0.0 if own else 0.0)
    elif e is not None and node.get("endMarker"):
        node["endMarker"] = ""
    return out


def _count_from(node: dict, m: float, top: bool) -> None:
    """In place: `node`'s plain times written in composition seconds, counted from its marker at `m` seconds instead
    (retime._shifted adds `m` back). A child with a marker of its own counts from that one and is left alone."""
    for k in node.get("keys", []):
        if not isinstance(k.get("t"), str):
            k["t"] = round(float(k["t"]) - m, 6)
    if not top and F.param(node["type"], "start") is not None and float(node.get("start", 0.0)) != 0.0:
        node["start"] = round(float(node["start"]) - m, 6)      # (a child at 0 starts with its group, as before)
    if F.param(node["type"], "end") is not None and not node.get("endMarker") and node.get("end", END_OF_COMP) < END_OF_COMP:
        node["end"] = round(float(node["end"]) - m, 6)
    for key in KEYED:
        for c in node.get(key, []):
            if not c.get("marker"):
                _count_from(c, m, False)


def _plain_keys(node: dict) -> None:
    """Time values become plain strings in the document (it holds only normal keys)."""
    for k in node.get("keys", []):
        if isinstance(k.get("t"), Time):
            k["t"] = str(k["t"])
    for v in node.values():
        if isinstance(v, list):
            for c in v:
                if isinstance(c, dict):
                    _plain_keys(c)


def _slug(s) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_") or "x"


def publish(build) -> None:
    """The script's markers into the project's: added, moved, renamed; this script's markers it no longer makes, removed."""
    mine, folder = _state(build).time_marks, _folder(build)
    doc = getattr(build, "doc", None)
    prefix = f"mk_script_{_slug(doc.item_id if doc is not None else 'main')}_{_slug(getattr(build, 'name', 'script'))}__"
    if folder is None:
        if mine:
            raise ValueError(f"marker(): this script runs outside a project, so there are no shared markers to add "
                             f"{', '.join(mine)} to; run it with run_script in a project")
        return
    rows = M.listing(folder)
    ours, calls = {r["id"]: r for r in rows if r["id"].startswith(prefix)}, []
    for name, at in mine.items():
        mid = prefix + _slug(name)
        other = next((r for r in rows if _key(r["name"]) == _key(name) and r["id"] != mid), None)
        if other is not None:
            if abs(float(other["at"]) - at) > 1e-3:
                raise ValueError(f'marker("{name}", {at:g}): "{other["name"]}" is already a project marker at {other["at"]:g} s '
                                 f'(made by {other["by"]}), not this script\'s. Time on it with "#{other["name"]}", or give yours another name')
            continue                                            # the same name at the same time is one marker
        r = ours.pop(mid, None)
        if r is None:
            calls.append({"op": "marker.add", "args": {"name": name, "at": at, "id": mid, "owner": "2d"}})
            continue
        if abs(float(r["at"]) - at) > 1e-6:
            calls.append({"op": "marker.move", "target": [mid], "args": {"at": at}})
        if r["name"] != name:
            calls.append({"op": "marker.rename", "target": [mid], "args": {"name": name}})
    calls += [{"op": "marker.remove", "target": [mid], "args": {}} for mid in ours]
    if calls:
        M.edit(folder, calls, Who.script(getattr(build, "name", "script")), label="Markers from the script")


def finish(build) -> None:
    for node, m in _state(build).time_from.values():
        _count_from(node, m, True)
    _plain_keys(build.root)          # publish() runs last, after run_source's checks: a failing script changes no marker


def for_script(build) -> dict:
    from .script_time_helpers import helpers
    _state(build)
    if not hasattr(build, "finishers"):
        build.finishers = []
    build.finishers.append(lambda: finish(build))
    return helpers(build)
