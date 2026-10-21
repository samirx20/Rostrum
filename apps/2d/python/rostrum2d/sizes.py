"""A layer's own size (its box before scale and turn), from its evaluated values: the one place, read by the agents'
geometry (mcp/geometry.py), the screen's boxes and auto layout (layout.py). A text has no size in the document, so
its box is an ESTIMATE from its size, letter spacing and letters: the engine has no measure call yet (request for Team Hem: stage2\2d-s13\request-for-hem-text-measure.md)."""
from __future__ import annotations

import math

TEXT_EM = 0.55            # average letter width in em, for the text box estimate


def own_size(layer_type: str, p: dict) -> tuple[float, float]:
    if layer_type == "text":
        lines = (p["body"] or " ").split("\n")
        longest = max(len(line) for line in lines)
        width = longest * p["size"] * (TEXT_EM + p["tracking"])
        if p["boxWidth"]:
            wrapped = sum(max(1, math.ceil(len(line) * p["size"] * TEXT_EM / p["boxWidth"])) for line in lines)
            return p["boxWidth"], wrapped * p["size"] * p["lineHeight"]
        return max(width, p["size"] * 0.5), len(lines) * p["size"] * p["lineHeight"]
    return p.get("w", 0.0), p.get("h", 0.0)
