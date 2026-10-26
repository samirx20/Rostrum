"""Hearing the whole song again: one call turns off every solo and/or mute (tracks, groups, the master). A solo left on
holds back every other track from the export, so the screen's "Solo on" line and the Export sheet call this too."""
from __future__ import annotations

from rostrum_core import Param

from .registry import REGISTRY

WHAT = {"solo": ("solo",), "mute": ("mute",), "both": ("solo", "mute")}


def listening(doc: dict) -> dict:
    """{"solo": [names], "mute": [names]} of the tracks and groups that are soloed / muted (tracks first)."""
    out = {"solo": [], "mute": []}
    for x in [*doc.get("tracks", []), *doc.get("buses", [])]:
        for k in out:
            if x.get(k):
                out[k].append(x.get("name") or x["id"])
    if any(m.get("mute") for m in doc.get("master", [])):
        out["mute"].append("Master")
    return out


@REGISTRY.operation("mix.hear_all", "Turn off every solo (what=solo), every mute (what=mute) or both (what=both) on the tracks, groups and "
                    "master, so the whole song plays and exports again. Solo and mute change what plays and what is exported.",
                    label="Hear everything", params=[Param.choice("what", list(WHAT), default="both", label="What to turn off",
                                                                   labels={"solo": "Solos", "mute": "Mutes", "both": "Solos and mutes"})])
def hear_all(ctx, targets, args):
    fields = WHAT[args.get("what", "both")]
    for x in [*ctx.doc.get("tracks", []), *ctx.doc.get("buses", []), *ctx.doc.get("master", [])]:
        for k in fields:
            if x.get(k):
                ctx.set(x["id"], k, False)
