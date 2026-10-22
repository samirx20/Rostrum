"""Moving and trimming a layer in time: `layer.shift` and `layer.trim` (the timeline's bar drags and agents both call them).

A layer counts its own times (`start`, `end`, its keys and everything inside it) from its marker, or its nearest timed
parent's, or from 0 (retime.py). Both operations keep that straight: moving a layer rebases every own time it owns, and
tying it to a marker means "this layer counts from that marker now", written so that nothing seen moves except what
the call asked for. Keys pinned on a marker ("#drop+0.2") and child layers with a marker of their own stay as they are.
Times the caller gives are composition seconds (the seconds the timeline shows).
"""
from __future__ import annotations

from rostrum_core import Param, markers
from rostrum_core.errors import codes
from rostrum_core.keys import marked
from rostrum_core.marker_times import lookup, split
from rostrum_core.tree import index

from . import fields as F
from .kind import REGISTRY as R
from .retime import CHILDREN, END, END_OF_COMP, FIELD, offset_of

_PROJECT = [None]        # the project folder whose shared markers these operations read (one project per process)


def use_project(folder) -> None:
    """The screen and the MCP server say which project's markers `to: "#name"` and `start: "#name"` mean."""
    _PROJECT[0] = folder


def times() -> dict:
    return markers.times(_PROJECT[0])


def _times(ctx) -> dict:
    """The markers of the document being edited: its own folder when the operation context carries one (`ctx.folder`),
    else the project `use_project` named."""
    folder = getattr(ctx, "folder", None)
    return markers.times(folder) if folder is not None else times()


def _marker(ctx, ref: str, what: str) -> tuple[str, float]:
    """(marker name, its seconds) for a bare "#name"; anything else, or a marker the project doesn't have, fails."""
    parts = split(ref)
    if parts is None or parts[1]:
        ctx.fail(codes.BAD_ARGUMENT, f'{what}="{ref}"', "is not a marker reference", ['"#drop"'],
                 "A marker alone, e.g. \"#logo lands\"; a time on a marker is not allowed here.")
    at = lookup(_times(ctx), parts[0])
    if at is None:
        ctx.fail(codes.NOT_FOUND, f'{what}="{ref}"', f'marker "{parts[0]}"', "is not in the project",
                 hint=f'Markers: {", ".join(sorted(_times(ctx))) or "none"}. Add it (edit_markers) first.')
    return parts[0], at


def _comp_fps(ctx, layer_id: str) -> float:
    idx = index(ctx.doc, ctx.kind.lists)
    loc = idx[layer_id]
    while loc.parent is not None and idx[loc.parent].item["type"] != "comp":
        loc = idx[loc.parent]
    return float(idx[loc.parent].item.get("fps", 30)) if loc.parent else 30.0


def _rebase(ctx, node: dict, delta: float, fps: float, top: bool = True) -> None:
    """Add `delta` to every own time inside `node` (its start and end, its keys, its drawing frames, and the same in
    everything it holds), except keys on a marker, an end on a marker, and child layers with a marker of their own."""
    if not delta or (not top and node.get(FIELD)):
        return
    if F.param(node["type"], "start") is not None:
        ctx.set(node["id"], "start", round(node.get("start", 0.0) + delta, 6))
    if not node.get(END) and F.param(node["type"], "end") is not None and node.get("end", END_OF_COMP) < END_OF_COMP:
        ctx.set(node["id"], "end", round(node["end"] + delta, 6))
    for k in node.get("keys", []):
        if not marked.marked(k):
            ctx.set(k["id"], "t", round(k["t"] + delta, 6))
    for f in node.get("frames", []):          # a drawing's frames are frame numbers of the composition
        ctx.set(f["id"], "at", f["at"] + round(delta * fps))
    for key in CHILDREN:
        for child in node.get(key, []):
            _rebase(ctx, child, delta, fps, False)


def _tie(ctx, layer: dict, name: str, delta: float) -> None:
    _rebase(ctx, layer, delta, _comp_fps(ctx, layer["id"]))
    ctx.set(layer["id"], FIELD, name)


@R.operation("layer.shift", "Move layers in time, with everything in them (their start and end, every key of the layer, its "
             "effects, masks, layers inside it and drawing frames). Keys on a marker and layers inside with a marker of their own "
             "stay where they are. Give `by` (seconds, + later, - earlier) or `to` (a marker such as \"#logo lands\": the layer "
             "is tied to it and its start lands exactly on it, so it follows when the marker moves).",
             target=F.LAYERS, label="Move in time",
             params=[Param.number("by", label="Move by", min=-36000, max=36000, step=0.01, unit=" s",
                                  help="Seconds to move; + is later"),
                     Param.text("to", label="Start on marker", help='A shared marker, "#name": the layer starts there and stays tied to it')])
def layer_shift(ctx, targets, args):
    if ("by" in args) == ("to" in args):
        ctx.fail(codes.BAD_ARGUMENT, "by / to", "needs exactly one of them", hint='by: 0.5 (seconds) or to: "#drop" (a marker).')
    name, at = _marker(ctx, args["to"], "to") if "to" in args else ("", 0.0)
    for t in targets:
        layer = ctx.item(t)
        if not name:
            _rebase(ctx, layer, float(args["by"]), _comp_fps(ctx, t))
        else:                                   # counted from the marker now, own start 0: every own time loses the old start
            _tie(ctx, layer, name, -float(layer.get("start", 0.0)))


def _ends(ctx, layer_id: str) -> tuple[float, float]:
    """(start, end) of a layer in composition seconds; end is infinity while it ends at the end of the composition."""
    layer, off = ctx.item(layer_id), offset_of(ctx.doc, layer_id, _times(ctx))
    end = _marker(ctx, "#" + layer[END], END)[1] if layer.get(END) else \
        (off + layer["end"] if layer.get("end", END_OF_COMP) < END_OF_COMP else float("inf"))
    return off + layer.get("start", 0.0), end


@R.operation("layer.trim", "Set when layers start and end, in composition seconds (the seconds the timeline shows). "
             "`start` / `end` as plain seconds: the layer shows from / until then, its keys stay where they are. "
             "`start: \"#marker\"`: the layer starts on that marker and counts its times from it from now on (tied), "
             "and nothing that is seen moves. `end: \"#marker\"`: the layer ends on that marker, wherever it moves.",
             target=F.LAYERS, label="Trim",
             params=[Param.number("start", label="Starts at", min=-36000, max=36000, step=0.01, unit=" s", markers=True,
                                  help='Composition seconds, or a marker "#name" (tied)'),
                     Param.number("end", label="Ends at", min=0, max=36000, step=0.01, unit=" s", markers=True,
                                  help='Composition seconds, or a marker "#name" (the layer ends on it)')])
def layer_trim(ctx, targets, args):
    if not args:
        ctx.fail(codes.BAD_ARGUMENT, "start / end", "needs at least one of them", hint='start: 1.5 or "#drop"; end: 4 or "#hit".')
    for t in targets:
        layer = ctx.item(t)
        if "start" in args:
            _trim_start(ctx, layer, args["start"])
        if "end" in args:
            _trim_end(ctx, layer, args["end"])
        start, end = _ends(ctx, t)
        if end <= start:
            ctx.fail(codes.BAD_ARGUMENT, f"{t}: start {start:g} s, end {end:g} s", "would end the layer before it starts",
                     hint="Move the start first, or end it later.")


def _trim_start(ctx, layer: dict, value) -> None:
    off = offset_of(ctx.doc, layer["id"], _times(ctx))
    if isinstance(value, str):
        name, at = _marker(ctx, value, "start")
        _tie(ctx, layer, name, off - at)        # same seen times, counted from the marker; the layer starts on it
        ctx.set(layer["id"], "start", 0.0)
    else:
        ctx.set(layer["id"], "start", round(value - off, 6))


def _trim_end(ctx, layer: dict, value) -> None:
    if isinstance(value, str):
        ctx.set(layer["id"], END, _marker(ctx, value, "end")[0])
        return
    if layer.get(END):
        ctx.set(layer["id"], END, "")
    ctx.set(layer["id"], "end", round(value - offset_of(ctx.doc, layer["id"], _times(ctx)), 6))
