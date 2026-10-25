"""How a shared marker that follows a 2D layer finds its time (rostrum_core.links; project-service CONTRACT.md § 3):
the layer's start (or end) in scene seconds, with the markers as they stand now. Registered through the entry point
group "rostrum.links" (pyproject.toml), so Sound keeps 2D's "Logo · sound" cue marker on its layer with 2D closed.
"""
from __future__ import annotations

from . import fields as F
from . import retime


def time_of(folder, item_id: str, part: str, use: str, times: dict, doc=None) -> float | None:
    """Seconds of layer `part`'s start / end in 2D item `item_id`; None when the layer is gone."""
    if doc is None:
        from rostrum_core import Document
        from .kind import KIND
        doc = Document.open(folder, item_id, KIND)
    played = retime.as_played(doc.data, part, times)     # the times the frames play: one rule (retime._start)
    if played is None:
        return None
    layer, comp = played
    end = float(layer.get("end", retime.END_OF_COMP))
    if use == "end" and end >= retime.END_OF_COMP:     # "End of comp": its composition's length
        return float(comp.get("duration", F.defaults("comp")["duration"]))
    return round(end if use == "end" else float(layer.get("start", 0.0)), 6)

