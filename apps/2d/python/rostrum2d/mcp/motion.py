"""look_motion: what moves and how, computed from the document's keys (nothing is rendered)."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from . import motion_checks as C
from .motion_facts import all_layers, layer_facts, r
from .pick import ITEM_COMP, comp_of

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
    comp = comp_of(ctx, args)
    a = analyse(comp, args.get("layers"))
    n = len(a["findings"])
    return Reply(f'{len(a["layers"])} layers, {n} finding{"s" * (n != 1)}.\n{describe(a)}', a)
