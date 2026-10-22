"""Everything wrong in one composition, as a list: what the inspect_diagnose tool returns and the screen's problems
list shows. Each problem: {kind, item, message, fix}; kinds in KINDS. Read-only: nothing here changes the document.

The checks come from the pieces that already decide each thing, never a second copy: the agents' geometry
(mcp/geometry.py: where a layer is and why it can't be seen), the expression checks (exprbake.problems), the
path-follow and track-matte links, the project's shared markers, and, with an engine, the engine itself (a font it
can't find, or anything else it refuses when the scene loads: a refused mask, feature or curve).
"""
from __future__ import annotations

import math
from pathlib import Path

from rostrum_core.keys import animated, key_value, keys_of, marked
from rostrum_core.marker_times import lookup

from . import fields as F, follow, render3d, retime
from .engine import EngineError
from .expr import ExprError, find
from .exprbake import exprs_of, items_of, parse_cached, problems as expr_problems
from .layoutbake import uses_layout
from .seen import unseen

KINDS = ("refused", "missing-font", "missing-file", "broken-link", "missing-marker", "expression",
         "invisible", "off-canvas", "unused-keys", "missing-render", "stale-render")


def _p(kind, item, message, fix=""):
    return {"kind": kind, "item": item, "message": message, "fix": fix}


def problems(comp: dict, folder=None, markers: dict | None = None) -> list[dict]:
    """The document-side problems (no engine). `markers`: the project's {name: seconds}; None = no project folder."""
    items = items_of(comp)
    exprs = exprs_of(items)
    out = [_p("broken-link", "", m, "Point it at a path layer beside it, or clear its Path field") for m in follow.problems(comp)]
    out += _links(items) + _files(items, folder) + _markers(exprs, markers) + _renders(items, folder)
    timing = _timed_from(items, markers)
    out += timing + [_p("expression", e.split(":", 1)[0], e, "Fix or clear the expression") for e in expr_problems(items, exprs)]
    if timing:                          # when layers show can't be told until every marker they name is there
        return out
    comp = retime.timed(comp, markers, comp.get("fps", 30))     # where and when layers show: composition time
    items = items_of(comp)
    try:
        out += _unseen(comp)
    except EngineError as e:            # a text the engine can't measure (its font, most often): no boxes to check
        out.append(_p("refused", "", f"Where the layers are can't be checked until every text can be measured: {e}",
                      "Fix the font (or what it names) first"))
    return out + _unused_keys(comp, items, exprs)


def _timed_from(items: dict, markers: dict | None) -> list[dict]:
    """Every marker the composition's times name that the project hasn't got (retime.py): a layer's Timed from /
    Ends at marker, or a key on a marker. Until they are there, nothing can be placed in time."""
    have = ", ".join(sorted(markers or {})) or "none yet"
    out = []

    def missing(item_id, name, what, fix):
        if lookup(markers or {}, name) is None:
            out.append(_p("missing-marker", item_id, f'{item_id} {what} marker "{name}", which the project has not got (it has: {have})',
                          f"Add the marker on the timeline (edit_markers), or {fix}"))
    for item in items.values():
        if item.get(retime.FIELD):
            missing(item["id"], item[retime.FIELD], "is timed from", "pick another in Timed from marker")
        if item.get(retime.END):
            missing(item["id"], item[retime.END], "ends at", "pick another in Ends at marker")
        for k in item.get("keys", []):
            if marked.marked(k):
                missing(k.get("id", item["id"]), marked.ref(k["t"]), "is a key on", "time the key in seconds")
    return out


def _links(items: dict) -> list[dict]:
    out = []
    for item in items.values():
        if item.get("matte"):
            parent = next((i for i in items.values() if item in i.get("layers", [])), None)
            siblings = parent.get("layers", []) if parent else []
            if not any(s["id"] == item["matte"] and s is not item for s in siblings):
                out.append(_p("broken-link", item["id"], f'{item["id"]}: its track matte "{item["matte"]}" is not a layer beside it',
                              "Pick a layer in the same group, or clear Track matte"))
    return out


def _files(items: dict, folder) -> list[dict]:
    out = []
    for item in items.values():
        for field in ("src", "lut"):
            path = item.get(field, "")
            if path and not (Path(path) if Path(path).is_absolute() else Path(folder or ".") / path).exists():
                out.append(_p("missing-file", item["id"], f'{item["id"]}.{field}: no file at "{path}"',
                              "Point it at the file again (absolute, or relative to the project folder)"))
    return out


def _renders(items: dict, folder) -> list[dict]:
    """3D render layers whose render can't be shown, or is older than its 3D document (render3d.py)."""
    out = []
    for item in items.values():
        if item["type"] == "render3d":
            st = render3d.status(item, folder)
            if not st["ok"]:
                out.append(_p("missing-render", item["id"], st["message"], "Render the 3D item (with EXR frames), or fix 3D item / Version"))
            elif st["stale"]:
                out.append(_p("stale-render", item["id"], f'{item["id"]}: {st["message"]}', "Render it again in Rostrum3D; this layer follows the newest render"))
    return out


def _markers(exprs: dict, markers: dict | None) -> list[dict]:
    out = []
    for (item, prop), src in sorted(exprs.items()):
        try:
            names = {n[2] for n in find(parse_cached(src), "marker")}
        except ExprError:
            continue                    # reported with the expression problems
        for name in sorted(names):
            if markers is None:
                out.append(_p("missing-marker", item, f'{item}.{prop} reads marker("{name}") but this document is not in a project folder',
                              "Open it in its project, or use a time in seconds"))
            elif name not in markers:
                have = ", ".join(sorted(markers)) or "none yet"
                out.append(_p("missing-marker", item, f'{item}.{prop} reads marker("{name}"), which the project doesn\'t have (it has: {have})',
                              "Add the marker on the timeline, or rename it in the expression"))
    return out


def _unseen(comp: dict) -> list[dict]:
    """Layers that can't be seen at any moment looked at (seen.py), in words: the commonest reason first."""
    out = []
    for lay_id, reasons in unseen(comp).items():
        top = max(reasons, key=reasons.get)
        kind = "off-canvas" if top == "outside the frame" else "invisible"
        out.append(_p(kind, lay_id, f"{lay_id} is never seen: {top}" + ("" if len(reasons) == 1 else f" (also: {', '.join(r for r in reasons if r != top)})"),
                      "Move it into the frame" if kind == "off-canvas" else "Check its opacity, size and start / end times"))
    return out


def _unused_keys(comp: dict, items: dict, exprs: dict) -> list[dict]:
    """Keys that change nothing: past the composition's end, outside the layer's own time, under an expression or an
    auto layout (which decide the field), or a field whose keys all hold one value."""
    duration, out = comp.get("duration", F.defaults("comp")["duration"]), []
    laid = uses_layout(comp)
    for item in items.values():
        if item["type"] not in F.ANIMATED_OWNERS:
            continue
        for prop in sorted(animated(item)):
            keys, where = keys_of(item, prop), f'{item["id"]}.{prop}'
            if (item["id"], prop) in exprs:
                out.append(_p("unused-keys", item["id"], f"{where}: {len(keys)} keys under an expression, which decides the field",
                              "Clear the expression or the keys"))
                continue
            if laid and prop in ("x", "y") and _laid_out(comp, item):
                out.append(_p("unused-keys", item["id"], f"{where}: keys on a layer its auto layout places", "Set it apart, or clear the keys"))
                continue
            late = [k for k in keys if k["t"] > duration + 1e-9]
            if late:
                out.append(_p("unused-keys", item["id"], f"{where}: {len(late)} key(s) after the composition ends ({duration:g} s)",
                              "Move them earlier or make the composition longer"))
            start, end = item.get("start", 0.0), item.get("end", math.inf)
            if item["type"] in F.LAYERS and keys and all(not start <= k["t"] < end for k in keys) and len(keys) > 1:
                out.append(_p("unused-keys", item["id"], f"{where}: every key is outside the layer's own time ({start:g}–{end:g} s)",
                              "Move the keys or the layer's start / end"))
            if len(keys) > 1 and all(key_value(k) == key_value(keys[0]) for k in keys):
                out.append(_p("unused-keys", item["id"], f"{where}: {len(keys)} keys that all hold {key_value(keys[0])!r}",
                              "Change one, or stop animating the field"))
    return out


def _laid_out(comp: dict, item: dict) -> bool:
    from .layout import has_layout
    parent = next((g for g in items_of(comp).values() if item in g.get("layers", [])), None)
    return bool(parent and has_layout(parent) and not item.get("layoutApart"))
