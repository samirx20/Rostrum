"""look_motion: what moves and how; look_path: the path one layer or the frame travels. Both computed from the document's
keys (nothing is rendered)."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from rostrum_core.keys import keys_of
from rostrum_core.keys.marked import order

from ..evaluate import value_at
from ..motion_samples import _cameras, _screen
from . import motion_checks as C
from .geometry import _apply, _invert, _mul, flatten
from ..boxes import matrix as box_matrix
from .motion_facts import all_layers, layer_facts, r
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


def _about(finding: dict) -> set[str]:
    return {*finding.get("layers", []), finding.get("layer", ""), finding.get("owner", "").split(".")[0]}


def analyse(comp: dict, only: list[str] | None = None) -> dict:
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    facts = [layer_facts(layer, fps, within) for layer, within in all_layers(comp)]
    findings = [*C.entrance_overlaps(facts), *C.quiet_spans(facts, duration), *C.not_showing(comp, duration - 1 / fps),
                *C.never_shown(comp, fps, duration), *C.dead_keys(comp, duration)]
    if only:
        known = [f["id"] for f in facts]
        for i in only:
            if i not in known:
                raise RostrumError.not_found("look_motion", "layer", i, known, "the layers of this composition")
        facts = [f for f in facts if f["id"] in only]
        findings = [x for x in findings if x["kind"] == "nothing_moves" or _about(x) & set(only)]
    return {"time": {"duration": r(duration, 3), "fps": fps}, "layers": facts, "findings": findings}


def describe(a: dict) -> str:
    lines = []
    for f in a["layers"]:
        if not f["moves"]:
            lines.append(f'{f["id"]}: still (no keys).')
            continue
        head = f'{f["id"]}: moves {f["moving"][0][0]}–{f["moving"][-1][1]} s; animates {", ".join(f["animated_fields"])}.'
        if f["path"]:
            p = f["path"]
            head += f' Path ({p["start"]}–{p["end"]} s): {p["from"]} → {p["to"]} px, peak {p["peak_speed_px_s"]} px/s at {p["peak_at"]} s.'
        for m in f["moves"]:
            if "jumps_at" in m:
                head += f' {m["field"]} jumps {m["from"]} → {m["to"]} at {m["end"]} s.'
            else:
                extra = f', overshoots by {m["overshoot"]}' if "overshoot" in m else ""
                head += f' {m["field"]} {m["start"]}–{m["end"]} s {m["from"]} → {m["to"]} ({m["ease"]}{extra}).' if "peak_rate" in m \
                    else f' {m["field"]} {m["start"]}–{m["end"]} s {m["from"]} → {m["to"]} ({m["ease"]}).'
        for h in f["holds"]:
            head += f' Holds {h["from"]}–{h["to"]} s.'
        lines.append(head)
    lines += [x["text"] for x in a["findings"]]
    return "\n".join(lines)


@tools.tool("look_motion", {"properties": {**ITEM_COMP, "layers": {"type": "array", "items": {"type": "string"}, "description": "Only these layer ids."}}})
def look_motion(ctx, args):
    """What moves and how, from the document's keys (no rendering): per layer when it moves, its path's start and end, peak speed,
    which fields animate, ease and overshoot, holds; plus facts: entrances that overlap, stretches where nothing moves,
    layers not on screen at the end or ever, keys that do nothing. Facts only, no scores."""
    comp = doc_and_comp(ctx, args)[1]                 # times as they play (pick.py)
    a = analyse(comp, args.get("layers"))
    n = len(a["findings"])
    return Reply(f'{len(a["layers"])} layers, {n} finding{"s" * (n != 1)}.\n{describe(a)}', a)


def _all_layers(layers: list[dict]):
    for layer in layers:
        yield layer
        yield from _all_layers(layer.get("layers", []))


def _seen_at(comp: dict, layer: dict, times: list[float]) -> list[tuple[float, float]]:
    """Where the layer's own place (x, y) is seen on screen at each time: through its groups and the frame (the one
    geometry rule, geometry.flatten); the frame: where the output's centre point lands (motion_samples)."""
    if layer["type"] == "camera":
        return [_screen(row)[:2] for row in _cameras(comp, times)[f'camera:{layer["id"]}']]
    out = []
    for t in times:
        node = next(n for n in flatten(comp, t) if n["id"] == layer["id"])
        outer = _mul(node["matrix"], _invert(box_matrix(node["props"], *node["size"])))     # the parent's matrix
        out.append(_apply(outer, node["props"]["x"], node["props"]["y"]))
    return out


def path_of(comp: dict, layer: dict, rate: float) -> dict:
    duration = float(comp.get("duration", 5.0))
    times = [min(i / rate, duration) for i in range(int(duration * rate) + 1)]
    seen = _seen_at(comp, layer, times)
    samples = [{"t": r(t, 4), "x": r(value_at(layer, "x", t), 2), "y": r(value_at(layer, "y", t), 2),
                "screen_x": r(sx, 2), "screen_y": r(sy, 2)} for t, (sx, sy) in zip(times, seen)]
    steps = [((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(seen, seen[1:])]
    xs, ys = ({k["t"]: k for k in keys_of(layer, f)} for f in ("x", "y"))
    handle = lambda side, t: ([xs.get(t, {}).get(side, None), ys.get(t, {}).get(side, None)]  # noqa: E731
                              if side in xs.get(t, {}) or side in ys.get(t, {}) else None)
    keys = [{"t": t, "x": xs[t]["v"] if t in xs else None, "y": ys[t]["v"] if t in ys else None,
             "out": handle("out", t), "in": handle("in", t)} for t in sorted({*xs, *ys}, key=order)]
    return {"layer": layer["id"], "rate": rate, "samples": samples, "keys": keys, "length_px": r(sum(steps), 1),
            "peak_speed_px_s": r(max(steps, default=0.0) * rate, 1)}


@tools.tool("look_path", {"required": ["layer"], "properties": {**ITEM_COMP,
    "layer": {"type": "string", "description": "A layer id, or the frame's id (\"frame\")."},
    "rate": {"type": "number", "exclusiveMinimum": 0, "maximum": 240, "description": "Samples a second. Default: the composition's frame rate."}}})
def look_path(ctx, args):
    """The path a layer or the frame travels, from the document's keys (no rendering): per sample t, its own x / y
    and where that point is seen on screen (through its groups and the frame; for the frame, where the output's centre
    lands); its position keys with their spatial handles (out / in as [dx, dy] px, null = none: a third of the way to
    the neighbouring key); the path's length on screen in px and its peak speed in px/s. Bend the path with the
    key.path_handles operation."""
    comp = doc_and_comp(ctx, args)[1]
    layers = {x["id"]: x for x in _all_layers(comp.get("layers", []))}
    if args["layer"] not in layers:
        raise RostrumError.not_found("look_path", "layer", args["layer"], list(layers), "the layers and the frame of this composition")
    a = path_of(comp, layers[args["layer"]], float(args.get("rate") or comp.get("fps", 30)))
    return Reply(f'{a["layer"]}: path {a["length_px"]} px on screen, peak {a["peak_speed_px_s"]} px/s, '
                 f'{len(a["keys"])} position key{"s" * (len(a["keys"]) != 1)}.', a)
