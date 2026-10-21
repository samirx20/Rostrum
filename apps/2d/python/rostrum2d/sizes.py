"""A layer's own size (its box before scale and turn), from its evaluated values: the one place, read by the agents'
geometry (mcp/geometry.py), the screen's boxes and auto layout (layout.py). A text has no size in the document: its
box is the one the engine lays it out in, measured and kept by textsize.py."""
from __future__ import annotations

from . import textsize


def own_size(layer_type: str, p: dict) -> tuple[float, float]:
    if layer_type == "text":
        return textsize.size(p)
    return p.get("w", 0.0), p.get("h", 0.0)
